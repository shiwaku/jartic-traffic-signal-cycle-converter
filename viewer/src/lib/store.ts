export type Listener<S> = (state: S, prev: S) => void

export interface Store<S> {
  get(): S
  /** 浅いマージで更新する。値が変わらなければ購読者は呼ばない。 */
  set(patch: Partial<S>): void
  subscribe(fn: Listener<S>): () => void
}

/**
 * 最小限のストア。UI と地図はここを購読するだけにして、互いを直接書き換えない。
 * フレームワークを入れるほどの規模ではないので、これだけを持つ。
 */
export function createStore<S extends object>(initial: S): Store<S> {
  let state = initial
  const listeners = new Set<Listener<S>>()

  return {
    get: () => state,
    set(patch) {
      const next = { ...state, ...patch }
      if ((Object.keys(patch) as (keyof S)[]).every((k) => Object.is(state[k], next[k]))) return
      const prev = state
      state = next
      for (const fn of listeners) fn(state, prev)
    },
    subscribe(fn) {
      listeners.add(fn)
      return () => listeners.delete(fn)
    },
  }
}
