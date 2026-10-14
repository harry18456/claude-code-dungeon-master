// What `gamectl.py book` prints (engine/core.py, op_book). The mod draws it as it comes.
export type BookExit = { id: string; title: string; label: string; open: boolean; hint?: string }

export type BookCell =
  | { kind: 'gap' }
  | { kind: 'node'; id: string; label: string; seen: boolean; here: boolean }
  | { kind: 'link'; axis: 'h' | 'v'; open: boolean; ends: [string, string] }

export type BookClue = { scene: string; title: string; text: string }

export type Book = {
  here: string
  title: string
  objective: string
  exits: BookExit[]
  map: { rows: BookCell[][] }
  clues: BookClue[]
  over: boolean
  version: number
}

export type BookTab = 'clues' | 'map'

// A ticket the engine minted this turn: [R:r-xxxxxx=N] in its dice lines
export type Ticket = { id: string; value: number }

// A finished turn's line: its duration as Claude Code reports it, its rolls and engine calls
export type Tally = { ms: number; rolled: number; calls: number }

// What the book found in the DM's reply, checked against the engine's tickets
export type Audit = { fake: string[]; missing: string[] }

declare module 'claude-code' {
  interface PluginState {
    // dice: the engine's dice lines of the turn in progress, one per entry
    // note: why the way the hero just tried is shut; '' when there is nothing to say
    // tried: the ways the engine has refused in this game, each as "scene>exit"
    // choices: the options the DM offered at the end of the last reply, in order
    // minted: the tickets the engine issued this turn; calls: engine tools called this turn
    // audit: tickets in the reply that the engine never issued, or issued but the DM left out
    // asked: the player's text this turn looked like an action (so a turn with no engine call is worth a note)
    // tally: each finished turn's rolls and engine calls, by the duration its line shows
    // ended: whether the story was over when the last main turn finished (or the session started)
    book: {
      book: Book | null; dice: string[]; tab: BookTab; note: string; tried: string[]
      choices: string[]; minted: Ticket[]; calls: number; audit: Audit; asked: boolean
      tally: Tally[]; ended: boolean
    }
  }
}
// $.store (across sessions): key "send" holds whether a picked choice is sent as the player's
// words at once instead of being filled into the prompt
