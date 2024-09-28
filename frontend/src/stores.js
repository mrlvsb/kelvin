import { writable } from 'svelte/store'

export const HideCommentsState = {
    NONE: "none",
    AUTOMATED: "automated",
    ALL: "all",
}
export const hideComments = writable(HideCommentsState.NONE)
