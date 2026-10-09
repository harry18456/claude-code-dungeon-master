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

declare module 'claude-code' {
  interface PluginState {
    // dice: the engine's dice lines of the turn in progress, one per entry
    // note: why the way the hero just tried is shut; '' when there is nothing to say
    // tried: the ways the engine has refused in this game, each as "scene>exit"
    book: { book: Book | null; dice: string[]; tab: BookTab; note: string; tried: string[] }
  }
}
