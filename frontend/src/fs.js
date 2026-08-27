import { computed, ref } from 'vue';
import { fetch } from './api.js';

/**
 * @typedef {import('./utilities/store-types').FileEntry} FileEntry
 *
 * @typedef {Object} OpenedFile
 * @property {string} [path]
 * @property {string} content
 * @property {boolean} [hide_tab]
 */

/** @type {import('vue').Ref<Record<string, OpenedFile>>} */
export const openedFiles = ref({});

/** @type {import('vue').Ref<string | null>} */
export const currentOpenedFile = ref(null);

/** @type {import('vue').Ref<string>} */
export const currentPath = ref('/');

// { root, endpoint_url } - the in-memory file tree and the backend endpoint.
/** @type {import('vue').Ref<{ root: Record<string, FileEntry>, endpoint_url: string | undefined }>} */
const fsState = ref({ root: {}, endpoint_url: undefined });

function dirname(path) {
    return absolutePath(path).split('/').splice(0, -1).join('/');
}

function basename(path) {
    const parts = path.split('/');
    return parts[parts.length - 1];
}

function normalizePath(path) {
    const parts = path.split('/');
    let result = [];
    for (const p of parts) {
        if (p) {
            if (p == '.') {
                continue;
            }

            if (p == '..') {
                result.pop();
            } else {
                result.push(p);
            }
        }
    }
    return '/' + result.join('/');
}

function absolutePath(path) {
    if (!path.startsWith('/')) {
        path = currentPath.value + '/' + path;
    }
    return normalizePath(path);
}

function getInode(path, root) {
    path = absolutePath(path);
    if (path == '/') {
        return { files: root };
    }

    const parts = path.split('/').slice(1);
    for (const dir of parts.slice(0, -1)) {
        root = root[dir]['files'];
    }

    return root[parts[parts.length - 1]];
}

/** Move one directory level up in the file browser. */
export function pathUp() {
    currentPath.value = normalizePath(currentPath.value + '/..');
}

/** Persist every opened file back to the backend. */
export async function saveOpenedFiles() {
    await Promise.all(
        Object.entries(openedFiles.value).map(([path, file]) => {
            return fetch(fsState.value.endpoint_url + path.slice(1), {
                method: 'PUT',
                body: file.content
            });
        })
    );
}

function closeFile(path) {
    if (openedFiles.value[path]) {
        delete openedFiles.value[path];
        const keys = Object.keys(openedFiles.value);
        currentOpenedFile.value = keys.length ? keys[0] : null;
    }
}

export const fs = {
    setRoot: (files, endpoint_url) => {
        openedFiles.value = {};
        currentOpenedFile.value = null;
        currentPath.value = '/';
        fsState.value = {
            root: files,
            endpoint_url
        };
    },
    setEndpointUrl: (endpoint_url) => {
        fsState.value.endpoint_url = endpoint_url;
    },
    createFile: (path, content) => {
        path = absolutePath(path);

        const parts = path.split('/');
        const dirInode = getInode(parts.slice(0, -1).join('/') || '/', fsState.value.root);
        dirInode['files'][parts[parts.length - 1]] = {
            type: 'file',
            content: content || ''
        };

        return path;
    },

    mkdir: (path) => {
        path = absolutePath(path);

        const dirInode = getInode(dirname(path), fsState.value.root);
        dirInode['files'][basename(path)] = {
            type: 'dir',
            files: {}
        };

        return path;
    },

    async rename(oldPath, newPath) {
        oldPath = absolutePath(oldPath);
        newPath = absolutePath(newPath);

        if (oldPath == newPath) {
            return;
        }

        await fetch(fsState.value.endpoint_url + oldPath.slice(1), {
            method: 'MOVE',
            headers: {
                Destination: newPath
            }
        });

        if (openedFiles.value[oldPath]) {
            openedFiles.value[newPath] = openedFiles.value[oldPath];
            delete openedFiles.value[oldPath];
        }

        if (currentOpenedFile.value == oldPath) {
            currentOpenedFile.value = newPath;
        }

        const oldName = basename(oldPath);
        const newName = basename(newPath);

        const oldInode = getInode(dirname(oldName), fsState.value.root);
        const newInode = getInode(dirname(newName), fsState.value.root);

        newInode['files'][newName] = oldInode['files'][oldName];
        delete oldInode['files'][oldName];
    },

    remove: async (path) => {
        path = absolutePath(path);
        await fetch(fsState.value.endpoint_url + path.slice(1), {
            method: 'DELETE'
        });
        const inode = getInode(dirname(path), fsState.value.root);
        delete inode['files'][basename(path)];
        closeFile(path);
    },

    close: (path) => {
        closeFile(path);
    },
    upload: async (path, file) => {
        path = absolutePath(path);
        await fetch(fsState.value.endpoint_url + path.slice(1), {
            method: 'PUT',
            body: file
        });

        const inode = getInode(dirname(path), fsState.value.root);
        inode['files'][basename(path)] = {
            type: 'file'
        };

        if (path in openedFiles.value) {
            let response = await fetch(fsState.value.endpoint_url + path.slice(1));
            let content = await response.text();
            openedFiles.value[path] = {
                path,
                content
            };
        }
    },

    open: async (path, opts = {}) => {
        if (!opts.hide_tab) {
            opts.hide_tab = false;
        }

        path = absolutePath(path);
        const inode = getInode(path, fsState.value.root);
        if (!inode) {
            return false;
        }

        if (inode.type == 'dir') {
            currentPath.value = path;
        } else {
            if (!(path in openedFiles.value)) {
                let content;
                if (inode.content == undefined) {
                    const res = await fetch(fsState.value.endpoint_url + path.slice(1));
                    content = await res.text();
                } else {
                    content = inode.content;
                }
                openedFiles.value[path] = {
                    path,
                    content,
                    ...opts
                };
            } else {
                openedFiles.value[path] = {
                    ...openedFiles.value[path],
                    ...opts
                };
            }

            if (!opts.hide_tab) {
                currentOpenedFile.value = path;
            }
        }

        return true;
    }
};

/**
 * Sorted listing (dirs first, then alphabetical) of the current directory.
 * @type {import('vue').ComputedRef<(FileEntry & { name: string })[]>}
 */
export const cwd = computed(() => {
    function map(ls) {
        return Object.entries(ls)
            .map(([name, inode]) => {
                return {
                    name,
                    ...inode
                };
            })
            .sort((a, b) => {
                if (a.type == b.type) {
                    return a.name < b.name ? -1 : 1;
                }
                return a.type < b.type ? -1 : 1;
            });
    }

    const inode = getInode(currentPath.value, fsState.value.root);
    return inode ? map(inode['files']) : [];
});
