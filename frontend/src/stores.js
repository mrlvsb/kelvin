import { writable } from 'svelte/store'

export const hideComments = writable({
    automated: false,
    student_teacher: false,
})
