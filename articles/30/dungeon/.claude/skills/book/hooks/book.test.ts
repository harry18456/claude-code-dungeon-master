import { test, expect } from 'claude-code/testing'

import { BACK, CELLAR, TAVERN } from './fixtures'

const SURFACES = ['terminal', 'desktop'] as const
const BAND = { hasSurvey: false, isWorking: true, maxRows: 10, bodyColumns: 80 } as any
const PANE = { title: '冒險手冊', isFocused: true, bodyColumns: 60, placement: 'dock' } as any

// The engine's answers to the DM, copied from a real run: one line per swing, tickets and all.
const AMBUSH = '巨鼠偷襲 1＋4＝5，對你的 AC 13，大失手 [R:r-d45b71=1]'
const SWINGS = [
  '攻擊巨鼠 18＋4＝22，對 AC 12，命中，傷害 6 [R:r-b3696a=18] [R:r-cec6ef=4]',
  '巨鼠反擊 1＋4＝5，對你的 AC 13，大失手 [R:r-23a3ee=1]',
  '另一隻巨鼠反擊 11＋3＝14，對你的 AC 13，命中，傷害 3 [R:r-ead002=11] [R:r-bb308d=3]',
]
const MOVE = JSON.stringify({ kind: 'move', rolls: [{ roll_id: 'r-d45b71' }], dice: AMBUSH, resolution_id: 'x-c0aa1839' })
const ATTACK = JSON.stringify({ kind: 'attack', rolls: [{ roll_id: 'r-b3696a' }], dice: SWINGS.join('\n'), resolution_id: 'x-78aae2f9' })
// get_state only reads: the last result sits inside it, and it commits nothing of its own
const STATE = JSON.stringify({ state: { hp: 12 }, version: 2, last_result: JSON.parse(ATTACK) })
const GUARD = '守衛擋在樓梯口，不讓你上去'
const WHY = `✕ 通往二樓的樓梯：${GUARD}`
const CURTAIN = '故事說完了。打 /report 可以寫成冒險日誌。'

// Stand-ins for everything beneath the plugin. `engine.book` is what gamectl prints now.
// move_to answers the way the real engine does: the guard refuses the stairs, the cellar
// door lets the hero through and the state changes with it.
function world(on: any, engine: { book: string; exitCode?: number; placed?: boolean }) {
  const seen = { asked: 0, registered: [] as any[], opened: [] as any[], filled: [] as any[], spinner: [] as any[], sent: [] as any[], store: {} as Record<string, unknown> }
  on('prompt.submit', ($: any, e: any) => {
    seen.sent.push(e)

    return { text: e.text }
  })
  // the dungeon folder is the cwd: gamectl.py is here, so the launcher stays as it is
  on('fs.exists', ($: any, e: any) => ({ value: e.path === 'gamectl.py' }))
  on('store.get', ($: any, e: any) => ({ value: seen.store[e.key] }))
  on('store.set', ($: any, e: any) => {
    seen.store[e.key] = e.value

    return { value: undefined }
  })
  on('process.run', () => {
    seen.asked += 1

    return { value: { exitCode: engine.exitCode ?? 0, stdout: engine.book, stderr: '', isStdoutTruncated: false, isStderrTruncated: false } }
  })
  on('tool.call', ($: any, e: any) => {
    if (e.tool === 'mcp__dungeon__resolve_attack') return { result: 'ok', text: ATTACK }
    if (e.tool === 'mcp__dungeon__get_state') return { result: 'ok', text: STATE }
    if (e.tool === 'mcp__dungeon__resolve_check') return { result: 'x', text: '梅拉不想理你', isError: true }
    if (e.tool === 'mcp__dungeon__move_to' && e.scene === 'upstairs') return { result: 'x', text: GUARD, isError: true }
    if (e.tool === 'mcp__dungeon__move_to') {
      engine.book = CELLAR

      return { result: 'ok', text: MOVE }
    }

    return { result: 'ok', text: 'ok' }
  })
  on('turn.start', ($: any, e: any) => ({ turnId: e.turnId }))
  on('turn.complete', ($: any, e: any) => ({ text: e.answer }))
  on('session.start', ($: any, e: any) => ({ cwd: e.cwd }))
  on('classic.SessionStart', () => ({}))
  on('command.register', ($: any, e: any) => {
    seen.registered.push(e)

    return { value: undefined }
  })
  on('ui.open', ($: any, e: any) => {
    seen.opened.push(e)

    return { value: { isPlaced: engine.placed ?? true } }
  })
  on('prompt.fill', ($: any, e: any) => {
    seen.filled.push(e)

    return { isFilled: true }
  })
  on('ui.render', { component: 'AbovePrompt' }, () => ({ type: 'Box', props: {}, children: [] }))
  // Claude Code draws the spinner from the props the mod hands down; keep them to look at
  on('ui.render', { component: 'TurnDuration' }, () => ({ type: 'Box', props: {}, children: [] }))
  on('ui.render', { component: 'Spinner' }, ($: any, e: any) => {
    seen.spinner.push(e.props)

    return { type: 'Box', props: {}, children: [] }
  })

  return seen
}

const start = ($: any, turnId: string, text = '我攻擊巨鼠') => $.turn.start({ turnId, text })
const complete = ($: any, turnId: string, agentId?: string, answer = 'done') =>
  $.turn.complete({ turnId, answer, durationMs: 1_000, isAborted: false, reason: 'answer', ...(agentId ? { agentId } : {}) })
// a reply the way CLAUDE.md asks for one: the dice line, then the question and its options
const REPLY = (dice: string) => `你揮劍砍中了巨鼠。\n\n骰子：\n${dice}\n\n你要做什麼？\n- 再砍一刀\n- 退回酒館\n- 搜一搜雜物堆\n`
const call = ($: any, tool: string, input: object = {}) => $.tool.call({ tool: `mcp__dungeon__${tool}`, ...input } as any)
const band = ($: any, surface: string, props: object = {}) =>
  $.ui.mount({ plugin: 'book', surface, component: 'AbovePrompt', props: { ...BAND, ...props } })
const pane = ($: any, surface: string, props: object = {}) =>
  $.ui.mount({ plugin: 'book', surface, component: 'Pane', props: { ...PANE, ...props }, requestId: 'book', viewport: { columns: 60, rows: 24 } as any })
const texts = async (ui: any): Promise<string[]> => (await ui.findAll({ type: 'Text' })).map((t: any) => t.text)
const buttons = async (ui: any, key = 'exit-') =>
  (await ui.findAll({ type: 'Button' })).filter((b: any) => String(b.props.key).startsWith(key)).map((b: any) => [b.props.hotkey, b.props.label])
const boxes = async (ui: any) => (await ui.findAll({ type: 'Box' })).map((b: any) => b.props)
const filled = (seen: { filled: any[] }) => seen.filled.map(f => [f.text, f.mode])
// a dice row is one Text holding the dim label and the line
const hasLine = (all: string[], line: string) => all.some(text => text.endsWith(line))

for (const surface of SURFACES) {
  test(`band on ${surface}: it says what the digits are for, then the engine's dice lines whole`, async ($, on) => {
    world(on, { book: TAVERN })
    await complete($, 't0')
    await start($, 't1')
    await call($, 'resolve_attack')
    await $.tool.call({ tool: 'Bash', command: 'ls' }) // not the engine

    const ui = await band($, surface)
    // no way looks shut before the hero has tried it
    expect(await buttons(ui)).toEqual([
      ['1', '酒館後面通往舊地窖的木門'],
      ['2', '通往二樓的樓梯'],
      ['3', '出鎮往北邊舊路'],
    ])
    const root = (await ui.find({ type: 'Box' })) as any
    expect(root.children[0].type).toBe('Box') // the exits come before the dice
    const drawn = await texts(ui)
    expect(drawn).toContain('要去哪裡？')
    expect(drawn).toContain('按數字或點一下')
    for (const line of SWINGS) expect(hasLine(drawn, line)).toBe(true)

    await start($, 't2') // a new turn: the dice leave, the exits stay
    expect(hasLine(await texts(ui), SWINGS[0]!)).toBe(false)
    expect((await buttons(ui)).length).toBe(3)
  })

  test(`band on ${surface}: a way is marked shut only after the engine refused it`, async ($, on) => {
    const seen = world(on, { book: TAVERN })
    await complete($, 't0')
    const ui = await band($, surface)

    await ui.press({ key: 'exit-upstairs' }) // untried: it writes the move like any other way
    expect(filled(seen)).toEqual([['我要去：通往二樓的樓梯', 'append']])

    await start($, 't1')
    await call($, 'resolve_check') // some other refusal marks nothing
    expect(await texts(ui)).not.toContain(WHY)
    await call($, 'move_to', { scene: 'upstairs' }) // the DM tries the stairs, the engine says no
    expect(await texts(ui)).toContain(WHY)
    expect(await buttons(ui)).toEqual([
      ['1', '酒館後面通往舊地窖的木門'],
      ['2', '通往二樓的樓梯 ✕'],
      ['3', '出鎮往北邊舊路'],
    ])

    await start($, 't2') // the reason leaves with the turn, the mark stays
    expect(await texts(ui)).not.toContain(WHY)
    await ui.press({ key: 'exit-upstairs' }) // a known shut way says why again and writes nothing
    expect(await texts(ui)).toContain(WHY)
    expect(seen.filled.length).toBe(1)

    await ui.press({ key: 'exit-cellar' })
    expect(filled(seen)[1]).toEqual(['我要去：酒館後面通往舊地窖的木門', 'append'])
    expect(await texts(ui)).not.toContain(WHY)
  })

  test(`pane on ${surface}: clues by scene, the map behind tab 2`, async ($, on) => {
    const seen = world(on, { book: BACK })
    await complete($, 't0')
    const ui = await pane($, surface)

    const page = await texts(ui)
    expect(page).toContain('目標：跟梅拉打聽地窖的怪聲')
    expect(page).toContain('【醉月酒館】')
    expect(page).toContain('【舊地窖】')
    expect(page.filter(t => t.startsWith('・')).length).toBe(2)

    await ui.press({ key: 'tab-map' })
    const map = await texts(ui)
    expect(map).toContain('醉月酒館')
    expect(map).toContain('───')
    expect(map).toContain('│')
    expect(map).not.toContain('─✕─') // the guarded stairs look like any other way until tried
    expect(map.some(t => t.startsWith('・'))).toBe(false)
    // every scene is a framed box; the one the hero stands in is the green one
    const framed = (await boxes(ui)).filter(p => p.borderStyle === 'round')
    expect(framed.length).toBe(4)
    expect(framed.filter(p => p.borderColor === 'green').length).toBe(1)
    // the scenes next door can be picked on the map itself, under the names the exits row uses
    expect(await buttons(ui, 'go-')).toEqual([
      [undefined, '出鎮往北邊舊路'],
      [undefined, '舊地窖'],
      [undefined, '通往二樓的樓梯'],
    ])
    await ui.press({ key: 'go-cellar' })
    expect(filled(seen)).toEqual([['我要去：舊地窖', 'append']])

    await start($, 't1')
    await call($, 'move_to', { scene: 'upstairs' })
    const after = await texts(ui)
    expect(after).toContain('─✕─')
    expect(after).toContain(WHY)
  })
}

test('a new game forgets the ways the last hero found shut', async ($, on) => {
  const engine = { book: JSON.stringify({ ...JSON.parse(TAVERN), version: 9 }) } // the tavern, later in a game
  world(on, engine)
  await complete($, 't0')
  await start($, 't1')
  await call($, 'move_to', { scene: 'upstairs' }) // the guard says no
  const ui = await band($, 'terminal')
  expect((await buttons(ui))[1]).toEqual(['2', '通往二樓的樓梯 ✕'])

  engine.book = TAVERN // /newgame: the state starts over, its version too
  await complete($, 't1')
  expect((await buttons(ui))[1]).toEqual(['2', '通往二樓的樓梯'])
})

test("the DM's options become buttons a-c, a pick fills the prompt, and they leave with the turn", async ($, on) => {
  const seen = world(on, { book: TAVERN })
  await complete($, 't0')
  await start($, 't1')
  await call($, 'resolve_attack')
  await complete($, 't1', undefined, REPLY(SWINGS.join('\n')))
  const ui = await band($, 'terminal', { isWorking: false })
  expect(await buttons(ui, 'choice-')).toEqual([
    ['a', '再砍一刀'], // drawn as a: 再砍一刀, the key once
    ['b', '退回酒館'],
    ['c', '搜一搜雜物堆'],
  ])
  expect((await texts(ui))).toContain('做什麼？')

  await ui.press({ key: 'choice-1' })
  expect(filled(seen)).toEqual([['退回酒館', 'append']])
  expect(seen.sent.length).toBe(0)

  await start($, 't2') // a new turn: the old options are gone, the DM is still talking
  expect((await buttons(ui, 'choice-')).length).toBe(0)
})

test('a choice naming a command fills the prompt with the command alone, even with /book send on', async ($, on) => {
  const seen = world(on, { book: TAVERN })
  await complete($, 't0')
  await $.command.run({ command: 'book', args: 'send' })
  await start($, 't1')
  // the DM cannot change gear; the option it offers is the player's command
  const reply = '靴子在你的背包裡。\n\n你要做什麼？\n- 換上軟底靴（打 `/dm-final:equip 軟底靴`）\n- 推開木門，下地窖\n- 去 2/3 的地方看看\n'
  await complete($, 't1', undefined, reply)
  const ui = await band($, 'terminal', { isWorking: false })
  await ui.press({ key: 'choice-0' })
  expect(filled(seen)).toEqual([['/dm-final:equip 軟底靴', 'replace']])
  expect(seen.sent.length).toBe(0) // Enter runs it: a command is never sent as words
  await ui.press({ key: 'choice-1' })
  await ui.press({ key: 'choice-2' }) // a slash inside words is no command
  expect(seen.sent.map(s => s.text)).toEqual(['推開木門，下地窖', '去 2/3 的地方看看'])
})

test('with /book send on, a pick goes out at once as the player', async ($, on) => {
  const seen = world(on, { book: TAVERN })
  await complete($, 't0')
  await $.command.run({ command: 'book', args: 'send' })
  expect(seen.store.send).toBe(true)
  await start($, 't1')
  await complete($, 't1', undefined, REPLY(AMBUSH))
  const ui = await band($, 'terminal', { isWorking: false })
  await ui.press({ key: 'choice-0' })
  expect(seen.sent.map(s => [s.text, s.origin?.kind, s.origin?.asUser])).toEqual([['再砍一刀', 'plugin', true]])
  expect(seen.filled.length).toBe(0)

  await $.command.run({ command: 'book', args: 'send' }) // again: off
  expect(seen.store.send).toBe(false)
})

test("the reply's tickets are checked against the engine's: a fake one and a missing one are called out", async ($, on) => {
  world(on, { book: TAVERN })
  await complete($, 't0')
  await start($, 't1')
  await call($, 'resolve_attack') // issues r-b3696a=18, r-cec6ef=4, r-23a3ee=1, r-ead002=11, r-bb308d=3
  // the DM keeps one ticket, drops the rest and invents one
  await complete($, 't1', undefined, REPLY('攻擊巨鼠 18＋4＝22 [R:r-b3696a=18] [R:r-ffffff=20]'))
  const ui = await band($, 'terminal')
  const line = (await texts(ui)).find(t => t.startsWith('查帳'))!
  expect(line).toContain('票根 r-ffffff=20 引擎沒發過')
  expect(line).toContain('引擎擲了 r-cec6ef=4，回覆裡沒貼')
  expect(line).not.toContain('r-b3696a')

  await start($, 't2')
  await complete($, 't2', undefined, REPLY(SWINGS.join('\n'))) // no engine call this turn: tickets written without a roll are fake
  expect((await texts(ui)).find(t => t.startsWith('查帳'))).toContain('r-b3696a=18 引擎沒發過')
})

test('an action the DM answered without asking the engine gets a note; a question does not', async ($, on) => {
  world(on, { book: TAVERN })
  await complete($, 't0')
  await start($, 't1', '我推開木門下地窖')
  await complete($, 't1', undefined, '你走下石階。\n\n你要做什麼？\n- 往前走\n')
  const ui = await band($, 'terminal', { isWorking: false })
  expect((await texts(ui)).some(t => t.includes('DM 沒問引擎'))).toBe(true)

  await start($, 't2', '這座鎮上有什麼傳聞？')
  await complete($, 't2', undefined, '傳聞是……\n\n你要做什麼？\n- 去問梅拉\n')
  expect((await texts(ui)).some(t => t.includes('DM 沒問引擎'))).toBe(false)

  await start($, 't3', '我攻擊巨鼠')
  await call($, 'resolve_attack')
  await complete($, 't3', undefined, REPLY(SWINGS.join('\n')))
  expect((await texts(ui)).some(t => t.includes('DM 沒問引擎'))).toBe(false)
})

test("the turn-ending line is retold with the turn's rolls and engine calls, and left alone without any", async ($, on) => {
  world(on, { book: TAVERN })
  const line = async () => {
    const ui = await $.ui.mount({ plugin: 'book', surface: 'terminal', component: 'TurnDuration', props: { word: 'Baked', durationMs: 12_400 } as any })

    return (await ui.findAll({ type: 'Text' })).map((t: any) => t.text)
  }
  await complete($, 't0')
  await start($, 't1', '這座鎮上有什麼傳聞？')
  expect(await line()).toEqual([]) // nothing happened: Claude Code's own line
  await start($, 't2')
  await call($, 'resolve_attack')
  await call($, 'get_state')
  expect(await line()).toEqual(['✻ Baked · 12 秒 · 擲了 5 次骰 · 問了引擎 2 次'])
})

test("an earlier turn's line, drawn again, keeps that turn's own rolls and engine calls", async ($, on) => {
  world(on, { book: TAVERN })
  const line = async (durationMs: number) => {
    const ui = await $.ui.mount({ plugin: 'book', surface: 'terminal', component: 'TurnDuration', props: { word: 'Baked', durationMs } as any })

    return (await ui.findAll({ type: 'Text' })).map((t: any) => t.text)
  }
  const end = (turnId: string, durationMs: number) =>
    $.turn.complete({ turnId, answer: 'done', durationMs, isAborted: false, reason: 'answer' } as any)
  await start($, 't1', '我跟梅拉打聽地窖')
  await call($, 'get_state')
  await end('t1', 10_200)
  await start($, 't2')
  await call($, 'resolve_attack')
  await call($, 'get_state')
  await end('t2', 12_400)
  expect(await line(10_200)).toEqual(['✻ Baked · 10 秒 · 擲了 0 次骰 · 問了引擎 1 次'])
  expect(await line(12_400)).toEqual(['✻ Baked · 12 秒 · 擲了 5 次骰 · 問了引擎 2 次'])
  await start($, 't3', '這座鎮上有什麼傳聞？')
  expect(await line(12_400)).toEqual(['✻ Baked · 12 秒 · 擲了 5 次骰 · 問了引擎 2 次']) // not the new turn's zeros
})

test("the spinner counts this turn's dice and is left alone without any", async ($, on) => {
  const seen = world(on, { book: TAVERN })
  const SPIN = { word: 'Thinking', message: null, suffix: '…', mode: 'responding' }
  const spinner = () => $.ui.mount({ plugin: 'book', surface: 'terminal', component: 'Spinner', props: SPIN as any })
  await complete($, 't0')
  await start($, 't1')
  await spinner()
  expect(seen.spinner.at(-1)).toEqual(SPIN) // no dice yet: Claude Code's own spinner

  await call($, 'resolve_attack') // three lines, five tickets: five rolls
  await spinner()
  expect(seen.spinner.at(-1)).toEqual({ ...SPIN, suffix: ' · 引擎擲了 5 次骰…' })

  await start($, 't2') // a new turn starts the count over
  await spinner()
  expect(seen.spinner.at(-1)).toEqual(SPIN)
})

test('a result that changed the state asks the engine again within the turn', async ($, on) => {
  const seen = world(on, { book: TAVERN })
  await complete($, 't0')
  await start($, 't1')
  expect(seen.asked).toBe(1)

  await call($, 'get_state') // reads only
  await call($, 'resolve_check') // the engine refused
  expect(seen.asked).toBe(1)

  await call($, 'move_to', { scene: 'cellar' })
  expect(seen.asked).toBe(2)
  const ui = await band($, 'terminal')
  expect(await buttons(ui)).toEqual([['1', '醉月酒館']]) // the cellar's exit, before the DM has finished
  expect(hasLine(await texts(ui), AMBUSH)).toBe(true)
})

test('a long fight: the exits stay on top and the oldest dice lines give way', async ($, on) => {
  world(on, { book: TAVERN })
  await complete($, 't0')
  await start($, 't1')
  for (let i = 0; i < 4; i += 1) await call($, 'resolve_attack') // 12 lines

  const ui = await band($, 'terminal', { maxRows: 6 })
  const root = (await ui.find({ type: 'Box' })) as any
  expect(root.children[0].type).toBe('Box')
  const drawn = await texts(ui)
  expect(drawn).toContain('明骰 前面還有 8 行')
  expect(drawn.filter(text => SWINGS.some(line => text.endsWith(line))).length).toBe(4)
})

test('after the ending the band offers no exits, and the book opened once on its clues', async ($, on) => {
  const engine = { book: TAVERN }
  const seen = world(on, engine)
  await complete($, 't0') // still playing: nothing opens
  expect(seen.opened.length).toBe(0)

  engine.book = JSON.stringify({ ...JSON.parse(TAVERN), over: true })
  await complete($, 't1') // the turn the story ended: the curtain call
  expect(seen.opened.map((o: any) => [o.id, o.focus])).toEqual([['book', true]])
  const ui = await band($, 'terminal')
  expect(await buttons(ui)).toEqual([])

  await complete($, 't2') // the next turn: it stays as the player left it
  expect(seen.opened.length).toBe(1)
})

test('the curtain call comes when the ending landed mid-turn, with the engine call that ended the story', async ($, on) => {
  const engine = { book: TAVERN }
  const seen = world(on, engine)
  await complete($, 't0')
  await start($, 't1', '我說出他的身分')
  engine.book = JSON.stringify({ ...JSON.parse(TAVERN), over: true })
  await call($, 'resolve_attack') // a committed result: the book is asked again within the turn
  expect(seen.opened.length).toBe(0) // the DM is still telling the ending
  await complete($, 't1')
  expect(seen.opened.map((o: any) => [o.id, o.focus])).toEqual([['book', true]])
  await complete($, 't2')
  expect(seen.opened.length).toBe(1)
})

test('in a terminal too narrow for the book to open by itself, the band still says the story is over', async ($, on) => {
  // Claude Code draws a pane a mod opens on its own only from 144 columns; below that it waits undrawn
  const engine = { book: TAVERN, placed: false }
  const seen = world(on, engine)
  await complete($, 't0')
  expect(await texts(await band($, 'terminal', { isWorking: false }))).not.toContain(CURTAIN)
  engine.book = JSON.stringify({ ...JSON.parse(TAVERN), over: true })
  await complete($, 't1')
  expect(seen.opened.length).toBe(1) // asked for, left undrawn
  const ui = await band($, 'terminal', { isWorking: false })
  expect(await buttons(ui)).toEqual([])
  expect(await texts(ui)).toContain(CURTAIN)
  await start($, 't2', '我回頭看看營地') // a later turn with no dice: the line stays
  await complete($, 't2')
  expect(await texts(await band($, 'terminal', { isWorking: false }))).toContain(CURTAIN)
})

test('a story that had ended before the session started gets no second curtain call', async ($, on) => {
  const seen = world(on, { book: JSON.stringify({ ...JSON.parse(TAVERN), over: true }) })
  await $.session.start({ cwd: '.', surface: 'terminal', isInteractive: true } as any)
  await start($, 't1', '我回頭看看營地')
  await complete($, 't1')
  expect(seen.opened.length).toBe(0)
})

test('a docked pane too narrow for full names still keeps each map row inside it', async ($, on) => {
  const seen = world(on, { book: BACK })
  await complete($, 't0')
  for (const bodyColumns of [36, 44, 60]) {
    const ui = await pane($, 'terminal', { bodyColumns })
    await ui.press({ key: 'tab-map' })
    const widths = (await boxes(ui)).map(p => p.width).filter(w => w !== undefined)
    expect(widths.slice(0, 5).reduce((a: number, b: number) => a + b, 0) <= bodyColumns).toBe(true)
    await ui.press({ key: 'tab-clues' })
    await ui.unmount()
  }

  // a name too long for its box is cut short on the map, and a pick still writes it whole
  const ui = await pane($, 'terminal', { bodyColumns: 36 })
  await ui.press({ key: 'tab-map' })
  expect((await buttons(ui, 'go-'))[0]).toEqual([undefined, '出鎮往…'])
  await ui.press({ key: 'go-old_road' })
  expect(filled(seen)).toEqual([['我要去：出鎮往北邊舊路', 'append']])
})

test('/book is there from the start and opens a focused pane with room for the map', async ($, on) => {
  const seen = world(on, { book: TAVERN })
  await $.session.start({ cwd: '.', surface: 'terminal', isInteractive: true } as any)
  expect(seen.registered.map(c => [c.name, c.immediate])).toEqual([['book', true]])
  expect(seen.asked).toBe(1)

  await $.command.run({ command: 'book', args: '', origin: { kind: 'composer' }, presentation: { isFullscreen: false, columns: 80 } } as any)
  expect(seen.opened).toEqual([{ id: 'book', title: '冒險手冊', focus: true, closeOnEscape: true, columns: 56, rows: 20 }])
  expect(seen.asked).toBe(2)
})

test('/clear starts over: the dice go and the engine is asked again', async ($, on) => {
  const seen = world(on, { book: TAVERN })
  await start($, 't1')
  await call($, 'resolve_attack')
  const asked = seen.asked

  await ($ as any).classic.SessionStart({ source: 'clear' })
  expect(seen.asked).toBe(asked + 1)
  const ui = await band($, 'terminal')
  expect(hasLine(await texts(ui), SWINGS[0]!)).toBe(false)

  await ($ as any).classic.SessionStart({ source: 'compact' }) // compaction keeps $.state
  expect(seen.asked).toBe(asked + 1)
})

test('a subagent ending its turn does not ask the engine again', async ($, on) => {
  const seen = world(on, { book: TAVERN })
  await complete($, 't1', 'agent-1')
  expect(seen.asked).toBe(0)
  await complete($, 't1')
  expect(seen.asked).toBe(1)
})

test('outside a dungeon folder: no exits, the dice still show, and the pane says so', async ($, on) => {
  world(on, { book: '無法執行：找不到 state.json', exitCode: 2 })
  await start($, 't1')
  await call($, 'resolve_attack')

  const ui = await band($, 'terminal')
  expect(await buttons(ui)).toEqual([])
  expect(await texts(ui)).not.toContain('要去哪裡？')
  expect(hasLine(await texts(ui), SWINGS[0]!)).toBe(true)

  const book = await pane($, 'terminal')
  expect((await book.find({ type: 'Text', text: /沒有地城/ }))?.type).toBe('Text')
})
