import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Book, BookCell, BookExit, BookTab } from '../types'

// The adventurer's book: what the status line and the settings hooks cannot do.
//   - the dice in the open: the engine's own dice lines above the prompt, as each roll lands
//   - picking a way: a digit at an empty prompt, or a click, writes "I go to ..." for an exit
//   - /book: a pane with the clues learned so far and a map with fog of war
// The mod works nothing out. It asks the engine (gamectl.py book) and draws the answer.
// One thing it holds back: a way looks open until the hero tries it and the engine refuses.

const PANE = 'book'
// tools/set_python.py rewrites the launcher in this line for people without uv
const ASK_ENGINE = 'uv run --no-project gamectl.py book'
const NODE = 16 // a scene's box on the map: its frame, then its name, up to seven CJK characters
const WAY = { h: '───', v: '│' }
const SHUT = { h: '─✕─', v: '✕' }
const LINK = WAY.h.length // a link's column is as wide as its drawing
const WIDE = /[ᄀ-ᅟ⺀-꓏가-힣豈-﫿︰-﹏＀-｠￠-￦]/

const book = atom({ plugin: 'book', key: 'book' } as const, null)
const dice = atom({ plugin: 'book', key: 'dice' } as const, [])
const tab = atom({ plugin: 'book', key: 'tab' } as const, 'clues')
const note = atom({ plugin: 'book', key: 'note' } as const, '')
const tried = atom({ plugin: 'book', key: 'tried' } as const, [])

const way = (scene: string, exit: string) => `${scene}>${exit}`
const why = (exit: BookExit) => `✕ ${exit.title}：${exit.hint ?? '這條路現在走不了'}`

// a label's width in terminal cells: a CJK or full-width character takes two
const cellsOf = (text: string) => [...text].reduce((n, ch) => n + (WIDE.test(ch) ? 2 : 1), 0)

// a label cut to the room in its box, ending in … when it does not fit
function fit(text: string, room: number): string {
  if (cellsOf(text) <= room) return text
  let out = ''
  for (const ch of text) {
    if (cellsOf(out + ch) + 1 > room) break
    out += ch
  }
  return `${out}…`
}

async function refresh($: EngineInterface): Promise<void> {
  try {
    const ran = await $.process.run(ASK_ENGINE.split(' '), { timeoutMs: 5_000 })
    if (ran.exitCode !== 0) return
    const fresh: Book = JSON.parse(ran.stdout)
    // a new game starts the state over and its version with it: the ways the last hero
    // found shut are not this hero's to know
    const before = await read($, book)
    if (before !== null && fresh.version < before.version) await update($, tried, () => [])
    await update($, book, () => fresh)
  } catch {
    // not a dungeon folder, or no launcher: the exits and the pane stay as they were
  }
}

// What one answer of the engine means here: its dice lines, and whether it changed the state.
function answerOf(text: string): { lines: string[]; hasCommitted: boolean } {
  try {
    const result = JSON.parse(text)
    const hasRolled = Array.isArray(result.rolls) && result.rolls.length > 0

    return {
      lines: hasRolled && typeof result.dice === 'string' ? result.dice.split('\n') : [],
      hasCommitted: typeof result.resolution_id === 'string',
    }
  } catch {
    return { lines: [], hasCommitted: false } // an error text, not the engine's JSON
  }
}

// The player picks a way: its digit, a click in the band, or a click on the map.
async function go($: EngineInterface, here: string, exit: BookExit): Promise<void> {
  const isKnownShut = !exit.open && (await read($, tried)).includes(way(here, exit.id))
  // a way already found shut says why again, at no cost; any other is the player's to send
  await update($, note, () => (isKnownShut ? why(exit) : ''))
  // append: what the player was typing stays in the box. The name is the one the band and
  // the map show, so what the player picked is what gets written.
  if (!isKnownShut) await $.prompt.fill({ text: `我要去：${exit.label}`, mode: 'append' })
}

// The engine refused a move. When it was a shut exit of this scene, the book marks it from now on.
async function refused($: EngineInterface, scene: unknown): Promise<void> {
  const now = await read($, book)
  const exit = now?.exits.find(one => one.id === scene)
  if (!now || !exit || exit.open) return

  const found = way(now.here, exit.id)
  await update($, tried, all => (all.includes(found) ? all : [...all, found]))
  await update($, note, () => why(exit))
}

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    // immediate: the book opens while the DM is still talking
    await $.command.register({ name: 'book', description: '打開冒險手冊：線索和地圖', immediate: true })
    await refresh($)

    return next(e)
  })

  // /clear, /resume and /branch reset $.state and raise no session.start
  on('classic.SessionStart', { source: ['clear', 'resume', 'fork'] }, async ($, e, next) => {
    await update($, dice, () => [])
    await update($, note, () => '')
    await refresh($)

    return next(e)
  })

  // a new turn: the dice of the last one leave the band
  on('turn.start', async ($, e, next) => {
    await update($, dice, () => [])
    await update($, note, () => '')

    return next(e)
  })

  // The engine's answer reaches the band before the DM retells it. A committed result
  // changed the state, so the exits and the map are asked again within the turn.
  on('tool.call', { tool: /^mcp__dungeon__/ }, async ($, e, next) => {
    const ran = await next(e)
    if (typeof ran.text !== 'string') return ran

    if (ran.isError === true) {
      if (String(e.tool).endsWith('__move_to')) await refused($, (e as unknown as { scene?: unknown }).scene)

      return ran
    }

    const answer = answerOf(ran.text)
    if (answer.lines.length > 0) await update($, dice, all => [...all, ...answer.lines])
    if (answer.hasCommitted) await refresh($)

    return ran
  })

  // /load and /newgame change the state without a tool call: ask once more
  // when the main turn ends (a subagent's turn carries an agentId)
  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) await refresh($)

    return next(e)
  })

  // Claude Code's own spinner, kept as it is but for its suffix: while the DM is still
  // talking, how many times the engine has rolled this turn (each roll leaves one ticket).
  on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
    const rolled = await read($, dice)
    const count = rolled.join('\n').match(/\[R:/g)?.length ?? 0
    if (count === 0) return next(e)

    return next({ ...e, props: { ...e.props, suffix: ` · 引擎擲了 ${count} 次骰…` } })
  })

  on('command.run', { command: 'book' }, async $ => {
    // columns and rows: room for the map, docked beside the transcript or above the prompt
    await $.ui.open({ id: PANE, title: '冒險手冊', focus: true, closeOnEscape: true, columns: 56, rows: 20 })
    await refresh($)

    return {}
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const now = await read($, book)
    const rolled = await read($, dice)
    const said = await read($, note)
    const found = await read($, tried)
    const exits = now === null || now.over ? [] : now.exits.slice(0, 9)

    if (e.props.hasSurvey || (exits.length === 0 && rolled.length === 0)) {
      return next(e)
    }

    const { Box, Button, Text } = $.ui.resolve(e)
    // The exits go first: a Button scrolled out of the band no longer takes its digit.
    const shown = rolled.slice(-Math.max(1, e.props.maxRows - (said === '' ? 2 : 3)))

    return (
      <Box flexDirection="column">
        {now !== null && exits.length > 0 && (
          <Box columnGap={2} flexWrap="wrap">
            <Text dimColor>要去哪裡？</Text>
            {exits.map((exit, i) => {
              const isKnownShut = !exit.open && found.includes(way(now.here, exit.id))

              return (
                <Button
                  key={`exit-${exit.id}`}
                  label={isKnownShut ? `${exit.label} ✕` : exit.label}
                  hotkey={String(i + 1)}
                  plain
                  dimColor={isKnownShut}
                  onPress={() => go($, now.here, exit)}
                />
              )
            })}
            <Text dimColor>按數字或點一下</Text>
          </Box>
        )}
        {said !== '' && (
          <Text dimColor wrap="wrap">
            {said}
          </Text>
        )}
        {rolled.length > shown.length && <Text dimColor>{`明骰 前面還有 ${rolled.length - shown.length} 行`}</Text>}
        {shown.map(line => (
          <Text wrap="wrap">
            <Text dimColor>明骰 </Text>
            {line}
          </Text>
        ))}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Button, Text } = $.ui.resolve(e)
    const now = await read($, book)
    const shown = await read($, tab)
    const found = await read($, tried)

    if (now === null) {
      return <Text dimColor>這個資料夾沒有地城。請在遊戲資料夾裡啟動 Claude Code。</Text>
    }

    const tabButton = (name: BookTab, label: string, hotkey: string) => (
      <Button
        key={`tab-${name}`}
        label={label}
        hotkey={hotkey}
        plain
        dimColor={shown !== name}
        onPress={() => update($, tab, () => name)}
      />
    )

    // a docked pane is narrow: the scenes' boxes give way, the links keep their width
    const scenes = ((now.map.rows[0]?.length ?? 1) + 1) / 2
    const room = Math.floor((e.props.bodyColumns - LINK * (scenes - 1)) / scenes)
    const node = Math.max(8, Math.min(NODE, room))
    const isKnownShut = (a: string, b: string) => found.includes(way(a, b)) || found.includes(way(b, a))

    // Scenes sit on the even rows and columns as framed boxes three rows high, the links
    // between them on the odd ones.
    const draw = (cell: BookCell, x: number, y: number) => {
      const width = x % 2 === 0 ? node : LINK
      const height = y % 2 === 0 ? 3 : 1

      if (cell.kind === 'node') {
        // the scene next door can be picked right here, under the name the exits give it;
        // the green box is where the hero stands
        const exit = cell.here ? undefined : now.exits.find(one => one.id === cell.id)
        const label = fit(exit?.label ?? cell.label, width - 2)

        return (
          <Box
            width={width}
            height={height}
            borderStyle="round"
            borderDimColor={!cell.seen}
            justifyContent="center"
            {...(cell.here ? { borderColor: 'green' } : {})}
          >
            {exit === undefined ? (
              <Text bold={cell.here} dimColor={!cell.seen} wrap="truncate" {...(cell.here ? { color: 'green' } : {})}>
                {label}
              </Text>
            ) : (
              <Button key={`go-${cell.id}`} label={label} plain dimColor={!cell.seen} onPress={() => go($, now.here, exit)} />
            )}
          </Box>
        )
      }
      if (cell.kind === 'link') {
        const isShut = !cell.open && isKnownShut(cell.ends[0], cell.ends[1])

        return (
          <Box width={width} height={height} justifyContent="center" alignItems="center">
            <Text dimColor>{(isShut ? SHUT : WAY)[cell.axis]}</Text>
          </Box>
        )
      }

      return <Box width={width} height={height} />
    }

    const clues =
      now.clues.length === 0 ? (
        <Text dimColor>還沒有線索。跟人說話、翻找東西，知道的事會記在這裡。</Text>
      ) : (
        <Box flexDirection="column">
          {now.clues.map((clue, i) => {
            const isNewScene = now.clues[i - 1]?.scene !== clue.scene

            return (
              <Box flexDirection="column" marginTop={isNewScene && i > 0 ? 1 : 0}>
                {isNewScene && <Text bold>【{clue.title}】</Text>}
                <Text wrap="wrap">・{clue.text}</Text>
              </Box>
            )
          })}
        </Box>
      )

    const map = (
      <Box flexDirection="column">
        {now.map.rows.map((row, y) => (
          <Box>{row.map((cell, x) => draw(cell, x, y))}</Box>
        ))}
        <Text> </Text>
        <Text dimColor wrap="wrap">
          綠框是你在的地方，暗的是還沒去過的地方。選旁邊的地方就能出發。
        </Text>
        {now.exits
          .filter(exit => !exit.open && isKnownShut(now.here, exit.id))
          .map(exit => (
            <Text wrap="wrap">{why(exit)}</Text>
          ))}
      </Box>
    )

    return (
      <Box flexDirection="column">
        <Box columnGap={3}>
          {tabButton('clues', '線索', '1')}
          {tabButton('map', '地圖', '2')}
        </Box>
        {now.objective !== '' && <Text dimColor>目標：{now.objective}</Text>}
        {now.over && <Text dimColor>故事說完了。打 /report 可以寫成冒險日誌。</Text>}
        <Text> </Text>
        {shown === 'clues' ? clues : map}
      </Box>
    )
  })
}
