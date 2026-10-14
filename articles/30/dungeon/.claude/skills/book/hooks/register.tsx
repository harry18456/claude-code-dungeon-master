import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { Audit, Book, BookCell, BookExit, BookTab, Tally, Ticket } from '../types'

// The adventurer's book: what the status line and the settings hooks cannot do.
//   - the dice in the open: the engine's own dice lines above the prompt, as each roll lands
//   - picking a way: a digit at an empty prompt, or a click, writes "I go to ..." for an exit
//   - picking a choice: the options the DM ends a reply with, a letter each; /book send
//     makes a pick go out at once as the player's words
//   - the tickets checked: a ticket in the reply the engine never issued, or one it issued
//     that the DM left out, is called out above the prompt as soon as the reply ends
//   - a turn the DM answered without asking the engine, while the player asked for an action
//   - /book: a pane with the clues learned so far and a map with fog of war
// The mod works nothing out. It asks the engine (gamectl.py book) and draws the answer.
// One thing it holds back: a way looks open until the hero tries it and the engine refuses.

const PANE = 'book'
const CHOICE_KEYS = ['a', 'b', 'c', 'd'] // the exits hold the digits
const ASKS = /(你要做什麼|要做什麼)[？?]/ // the line the DM ends a reply with, per CLAUDE.md
const TICKET = /[[［]R:(r-[0-9a-f]{6})=(\d+)[\]］]/g // a ticket, full-width brackets included
// what the player typed looked like an action (so a turn with no engine call is worth a note);
// a question, a slash command or a bare word is not
const BULLET = /^[-・•]\s*/ // -, ・ or • at the start of an option line
// a player's command inside an option (`/equip 軟底靴`, 打 /dm-final:equip 軟底靴): the DM cannot run it
const COMMAND = /(?:^|[\s`（(：:])(\/[A-Za-z][\w-]*(?::[\w-]+)?(?:[ \t]+[^`）)\n]+)?)/
// control characters, zero-width marks, bidi controls and the BOM: dropped before text goes into the prompt
const UNSEEN = new RegExp('[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u206f\ufeff]', 'g')
const ACTION = /^(?!\/)(?=.*(我|去|打|攻|搜|翻|偷|說服|問|買|拿|走|推|開|跟|找|試|塞|給))(?!.*[？?]$)/
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
const choices = atom({ plugin: 'book', key: 'choices' } as const, [])
const minted = atom({ plugin: 'book', key: 'minted' } as const, [])
const calls = atom({ plugin: 'book', key: 'calls' } as const, 0)
const audit = atom({ plugin: 'book', key: 'audit' } as const, { fake: [], missing: [] })
const asked = atom({ plugin: 'book', key: 'asked' } as const, false)
const tally = atom({ plugin: 'book', key: 'tally' } as const, [] as Tally[])
const TALLIED = 50 // finished turns whose line keeps its own numbers
// the story's end as the last finished turn saw it: the engine call that ends the story asks
// the book again mid-turn, so the book itself has already turned over by the turn's end
const ended = atom({ plugin: 'book', key: 'ended' } as const, false)
// the story's end in one line: in the band where the exits were, and under the book's goal
const CURTAIN = '故事說完了。打 /report 可以寫成冒險日誌。'

const way = (scene: string, exit: string) => `${scene}>${exit}`
// each roll leaves one ticket in the dice lines
const rollsIn = (lines: string[]) => lines.join('\n').match(/\[R:/g)?.length ?? 0
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

// The launcher: gamectl.py in the dungeon folder, or inside the dm plugin (where this mod
// sits under skills/book/ and gamectl.py at the plugin's root). The engine writes the
// save into the project either way.
async function launcher($: EngineInterface): Promise<string[]> {
  const argv = ASK_ENGINE.split(' ')
  const here = `${$.plugin.root}/gamectl.py`
  if (!(await $.fs.exists('gamectl.py')) && (await $.fs.exists(here))) {
    return argv.map(a => (a === 'gamectl.py' ? here : a))
  }
  return argv
}

async function refresh($: EngineInterface): Promise<void> {
  try {
    const ran = await $.process.run(await launcher($), { timeoutMs: 5_000 })
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

// What one answer of the engine means here: its dice lines, the tickets in them, and whether
// it changed the state.
function answerOf(text: string): { lines: string[]; tickets: Ticket[]; hasCommitted: boolean } {
  try {
    const result = JSON.parse(text)
    const hasRolled = Array.isArray(result.rolls) && result.rolls.length > 0
    const lines = hasRolled && typeof result.dice === 'string' ? result.dice.split('\n') : []

    return { lines, tickets: ticketsIn(lines.join('\n')), hasCommitted: typeof result.resolution_id === 'string' }
  } catch {
    return { lines: [], tickets: [], hasCommitted: false } // an error text, not the engine's JSON
  }
}

function ticketsIn(text: string): Ticket[] {
  return [...text.matchAll(TICKET)].map(m => ({ id: m[1]!, value: Number(m[2]) }))
}

// The options the DM ends a reply with: the "- " lines after 你要做什麼？, at most four.
// Control characters and invisible marks are dropped: the text goes into the prompt.
function choicesIn(answer: string): string[] {
  const at = answer.search(ASKS)
  if (at < 0) return []
  const tail = answer.slice(at).split('\n').slice(1)
  const out: string[] = []
  for (const raw of tail) {
    const line = raw.trim()
    if (line === '') continue
    if (!BULLET.test(line)) break
    const text = line.replace(BULLET, '').replace(UNSEEN, '').trim()
    if (text !== '' && text.length <= 80) out.push(text)
    if (out.length === CHOICE_KEYS.length) break
  }
  return out
}

// Day 13's audit, done here as the reply ends: tickets the DM wrote that the engine never
// issued (or with another value), and tickets the engine issued that the reply left out.
function auditOf(answer: string, issued: Ticket[]): Audit {
  const written = ticketsIn(answer)
  const fake = written.filter(w => !issued.some(t => t.id === w.id && t.value === w.value)).map(w => `${w.id}=${w.value}`)
  const missing = issued.filter(t => !written.some(w => w.id === t.id)).map(t => `${t.id}=${t.value}`)
  return { fake: [...new Set(fake)], missing: [...new Set(missing)] }
}

// The player picks one of the DM's options: into the prompt, or sent at once when /book send is on.
async function pick($: EngineInterface, text: string): Promise<void> {
  // an option that names a command puts the command alone in the prompt, and Enter runs it;
  // sent as words, it would only go back to the DM, who cannot change the hero's gear
  const command = text.match(COMMAND)?.[1]?.trim()
  if (command) return void (await $.prompt.fill({ text: command, mode: 'replace' }))
  const send = (await $.store.get('send')) === true
  if (send) await $.prompt.submit({ text, asUser: true })
  else await $.prompt.fill({ text, mode: 'append' })
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
    const over = (await read($, book))?.over === true
    await update($, ended, () => over) // a story already told gets no second curtain call

    return next(e)
  })

  // /clear, /resume and /branch reset $.state and raise no session.start
  on('classic.SessionStart', { source: ['clear', 'resume', 'fork'] }, async ($, e, next) => {
    await update($, dice, () => [])
    await update($, note, () => '')
    await refresh($)
    const over = (await read($, book))?.over === true
    await update($, ended, () => over)

    return next(e)
  })

  // a new turn: the dice, the choices and the audit of the last one leave the band
  on('turn.start', async ($, e, next) => {
    await update($, dice, () => [])
    await update($, note, () => '')
    await update($, choices, () => [])
    await update($, minted, () => [])
    await update($, calls, () => 0)
    await update($, audit, () => ({ fake: [], missing: [] }))
    await update($, asked, () => ACTION.test(e.text.trim()))

    return next(e)
  })

  // The engine's answer reaches the band before the DM retells it. A committed result
  // changed the state, so the exits and the map are asked again within the turn.
  // the engine's tools, in the dungeon folder (mcp__dungeon__*) or inside a plugin
  // (mcp__plugin_<plugin>_dungeon__*, whatever the plugin is called)
  on('tool.call', { tool: /^mcp__(plugin_[\w-]+_)?dungeon__/ }, async ($, e, next) => {
    await update($, calls, n => n + 1)
    const ran = await next(e)
    if (typeof ran.text !== 'string') return ran

    if (ran.isError === true) {
      if (String(e.tool).endsWith('__move_to')) await refused($, (e as unknown as { scene?: unknown }).scene)

      return ran
    }

    const answer = answerOf(ran.text)
    if (answer.lines.length > 0) await update($, dice, all => [...all, ...answer.lines])
    if (answer.tickets.length > 0) await update($, minted, all => [...all, ...answer.tickets])
    if (answer.hasCommitted) await refresh($)

    return ran
  })

  // /load, /newgame and /equip change the state without a tool call: ask once more
  // when the main turn ends (a subagent's turn carries an agentId). The reply itself is
  // read for the DM's options and checked against the engine's tickets.
  on('turn.complete', async ($, e, next) => {
    if (e.agentId === undefined) {
      // the turn's line is drawn again later (a scroll, a resize): it keeps this turn's numbers
      const rolled = rollsIn(await read($, dice))
      const n = await read($, calls)
      await update($, tally, all => [...all.filter(t => t.ms !== e.durationMs), { ms: e.durationMs, rolled, calls: n }].slice(-TALLIED))
      const wasOver = await read($, ended)
      await refresh($)
      const isOver = (await read($, book))?.over === true
      await update($, ended, () => isOver)
      const issued = await read($, minted)
      await update($, choices, () => choicesIn(e.answer))
      await update($, audit, () => auditOf(e.answer, issued))
      // the story just ended: the book opens on its clues, a curtain call (a pane opened by
      // a hook must take focus; Esc hands the keyboard back)
      if (!wasOver && isOver) {
        await update($, tab, () => 'clues')
        await $.ui.open({ id: PANE, title: '冒險手冊', focus: true, closeOnEscape: true, columns: 56, rows: 20 })
      }
    }

    return next(e)
  })

  // Claude Code's own turn-ending line, retold as the game's: the reply's word is kept,
  // then the seconds, the rolls and the calls to the engine this turn.
  on('ui.render', { component: 'TurnDuration' }, async ($, e, next) => {
    const { Text } = $.ui.resolve(e)
    // a finished turn's own numbers; the turn that just ended may draw before its tally lands
    const kept = (await read($, tally)).find(t => t.ms === e.props.durationMs)
    const rolled = kept?.rolled ?? rollsIn(await read($, dice))
    const n = kept?.calls ?? (await read($, calls))
    if (rolled === 0 && n === 0) return next(e)
    const secs = Math.round(e.props.durationMs / 1000)

    return (
      <Text dimColor>
        {`✻ ${e.props.word} · ${secs} 秒 · 擲了 ${rolled} 次骰 · 問了引擎 ${n} 次`}
      </Text>
    )
  })

  // Claude Code's own spinner, kept as it is but for its suffix: while the DM is still
  // talking, how many times the engine has rolled this turn (each roll leaves one ticket).
  on('ui.render', { component: 'Spinner' }, async ($, e, next) => {
    const rolled = await read($, dice)
    const count = rolled.join('\n').match(/\[R:/g)?.length ?? 0
    if (count === 0) return next(e)

    return next({ ...e, props: { ...e.props, suffix: ` · 引擎擲了 ${count} 次骰…` } })
  })

  on('command.run', { command: 'book' }, async ($, e) => {
    // /book send: a picked choice goes out at once as the player's words; again to turn it off
    if (e.args.trim() === 'send') {
      const send = (await $.store.get('send')) !== true
      await $.store.set('send', send)

      return { text: send ? '選項按下去就直接送出。再打一次 /book send 關掉。' : '選項按下去只填進輸入框，按 Enter 才送。' }
    }
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
    const offered = e.props.isWorking ? [] : await read($, choices) // the options belong to the reply that ended
    const checked = await read($, audit)
    const quiet = !e.props.isWorking && (await read($, asked)) && (await read($, calls)) === 0
    const exits = now === null || now.over ? [] : now.exits.slice(0, 9)
    // the story is over: the line stays every turn, since the book opens by itself only in a
    // terminal wide enough for a pane nobody asked for (144 columns), and waits undrawn below that
    const over = now?.over === true

    if (e.props.hasSurvey || (exits.length === 0 && rolled.length === 0 && offered.length === 0 && !over)) {
      return next(e)
    }

    const { Box, Button, Text } = $.ui.resolve(e)
    // The exits and the choices go first: a Button scrolled out of the band no longer takes its key.
    const fixed = (said === '' ? 2 : 3) + (offered.length > 0 ? 1 : 0) + (checked.fake.length + checked.missing.length > 0 ? 1 : 0) + (quiet ? 1 : 0)
    const shown = rolled.slice(-Math.max(1, e.props.maxRows - fixed))

    return (
      <Box flexDirection="column">
        {offered.length > 0 && (
          <Box columnGap={2} flexWrap="wrap">
            <Text dimColor>做什麼？</Text>
            {offered.map((text, i) => (
              <Button key={`choice-${i}`} label={text} hotkey={CHOICE_KEYS[i]!} plain onPress={() => pick($, text)} />
            ))}
          </Box>
        )}
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
        {over && <Text dimColor>{CURTAIN}</Text>}
        {said !== '' && (
          <Text dimColor wrap="wrap">
            {said}
          </Text>
        )}
        {(checked.fake.length > 0 || checked.missing.length > 0) && (
          <Text color="red" wrap="wrap">
            {`查帳 ${[
              ...checked.fake.map(t => `票根 ${t} 引擎沒發過`),
              ...checked.missing.map(t => `引擎擲了 ${t}，回覆裡沒貼`),
            ].join('；')}`}
          </Text>
        )}
        {quiet && <Text color="yellow">這回合 DM 沒問引擎，世界沒有變。想真的做，再說一次或選一個出口。</Text>}
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
        {now.over && <Text dimColor>{CURTAIN}</Text>}
        <Text> </Text>
        {shown === 'clues' ? clues : map}
      </Box>
    )
  })
}
