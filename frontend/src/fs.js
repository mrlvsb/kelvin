import { get, writable, derived } from 'svelte/store';
import {fetch} from './api.js'

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
  for(const p of parts) {
    if(p) {
      if(p == '.') {
        continue;
      }

      if(p == '..') {
        result.pop();
      } else {
        result.push(p);
      }
    }
  }
  return '/' + result.join('/');
}

function absolutePath(path) {
    if(!path.startsWith('/')) {
      path = get(currentPath) + '/' + path;
    }
    return normalizePath(path);
}

function getInode(path, root) {
  path = absolutePath(path);
  if(path == '/') {
    return {'files': root};
  }

  const parts = path.split('/').slice(1);
  for(const dir of parts.slice(0, -1)) {
    root = root[dir]['files'];
  }

  return root[parts[parts.length - 1]];
}

function createFs() {
  const { subscribe, set, update } = writable({'root': {}});

  return {
    subscribe,
    setRoot: (files, endpoint_url) => {
      openedFiles.set([]);
      currentOpenedFile.set(null)
      currentPath.set('/');
      set({
        'root': files,
        endpoint_url
      })
    },
    setEndpointUrl: (endpoint_url) => {
      update(conf => {
        conf['endpoint_url'] = endpoint_url;
        return conf;
      })
    },
    createFile: (path, content) => {
      path = absolutePath(path);

      update(fs => {
        const parts = path.split('/');
        const dirInode = getInode(parts.slice(0, -1).join('/'), fs['root']);
        dirInode['files'][parts[parts.length - 1]] = {
          'type': 'file',
          'content': content || '',
        };

        return fs;
      });

      return path;
    },

    mkdir: (path) => {
      path = absolutePath(path);

      update(fs => {
        const dirInode = getInode(dirname(path), fs['root']);
        dirInode['files'][basename(path)] = {
          'type': 'dir',
          'files': {},
        };

        return fs;
      });

      return path;
    },

    async rename(oldPath, newPath) {
      oldPath = absolutePath(oldPath);
      newPath = absolutePath(newPath);

      if(oldPath == newPath) {
        return;
      }

      const res = await fetch(get(fs)['endpoint_url'] + oldPath.slice(1), {
        method: 'MOVE',
        headers: {
          'Destination': newPath,
        }
      });

      openedFiles.update(openedFiles => {
        if(openedFiles[oldPath]) {
          openedFiles[newPath] = openedFiles[oldPath];
          delete openedFiles[oldPath];
        }
        return openedFiles;
      });

      currentOpenedFile.update(current => {
        return current == oldPath ? newPath : current;
      });

      const oldName = basename(oldPath);
      const newName = basename(newPath);

      update(fs => {
        const oldInode = getInode(dirname(oldName), fs['root']);
        const newInode = getInode(dirname(newName), fs['root']);

        newInode['files'][newName] = oldInode['files'][oldName];
        delete oldInode['files'][oldName];

        return fs;
      });
    },

    remove: async (path) => {
      path = absolutePath(path);
      await fetch(get(fs)['endpoint_url'] + path.slice(1), {
        method: 'DELETE',
      });
      update(fs => {
        const inode = getInode(dirname(path), fs['root']);
        delete inode['files'][basename(path)];
        return fs;
      });

      openedFiles.update(openedFiles => {
        if(openedFiles[path]) {
          delete openedFiles[path];

          currentOpenedFile.update(current => {
            return Object.keys(openedFiles).length ? Object.keys(openedFiles)[0] : null;
          });
        }
        return openedFiles;
      });

    },

    upload: async (path, file) => {
      path = absolutePath(path);
      await fetch(get(fs)['endpoint_url'] + path.slice(1), {
        method: 'PUT',
        body: file,
      });

      update(fs => {
        const inode = getInode(dirname(path), fs['root']);
        inode['files'][basename(path)] = {
          type: 'file',
        };
        return fs;
      });
    },

    open: async (path) => {
      path = absolutePath(path);
      const inode = getInode(path, get(fs)['root']);
      if(!inode) {
        return;
      }

      if(inode.type == 'dir') {
        currentPath.set(path);
      } else {
        if(!(path in get(openedFiles))) {
          let content;
          if(inode.content == undefined) {
            const res = await fetch(get(fs)['endpoint_url'] + path.slice(1));
            content = await res.text();
          } else {
            content = inode.content;
          }
          openedFiles.update(files => {
            files[path] = {
              path,
              content,
            };

            return files;
          });
        }

        currentOpenedFile.set(path);
      }
    }
  };
};

function createPath() {
  const { subscribe, set, update } = writable('/');

  return {
    subscribe,
    set,
    up: () => update(path => normalizePath(path + '/..')),
  }
}

function createOpenedFiles() {
  const { subscribe, set, update } = writable([]);

  return {
    subscribe,
    set,
    update,
    save: async () => {
      await Promise.all(Object.entries(get(openedFiles)).map(([path, file]) => {
        return fetch(get(fs)['endpoint_url'] + path.slice(1), {
          method: 'PUT',
          body: file.content,
        });
      }));
    }
  }
}

export const openedFiles = createOpenedFiles();
export const currentOpenedFile = writable();
export const fs = createFs();
export const currentPath = createPath(); 
export const cwd = derived([fs, currentPath], ([$fs, $path], set) => {
  function map(ls) {
    return Object.entries(ls).map(([name, inode]) => {
      return {
        name,
        ...inode
      };
    }).sort((a, b) => {
        if(a.type == b.type) {
          return a.name < b.name ? -1 : 1;
        }
        return a.type < b.type ? -1 : 1;
    });
  }
  set(map(getInode($path, $fs['root'])['files']));
}, []);
