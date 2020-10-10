<style>
.tree {
  width: 200px;
}
.tree ul {
  list-style: none;
  padding: 0;
}

.tree ul li {
  cursor: pointer;
}

.newdir {
  white-space: nowrap;
}

ul input {
  width: max-content;
  padding: 0px;
}

.action-buttons span {
  cursor: pointer;
}

</style>

<script>
  import {clickOutside} from './utils.js';

  export let files;
	let current = null;
  export let openedFiles = {};

	let path = [];
  export let files_uri;

  function getInode(path) {
    if(path.length == 0) {
      return {'files': files};
    }

    let root = files;
    const parts = path.split('/');
    for(const dir of parts.slice(0, -1)) {
      root = root[dir]['files'];
    }

    return root[parts[parts.length - 1]];
  }

  $: dirFiles = getInode(path.join('/'))['files'];

  async function openFile(path) {
    if(!(path in openedFiles)) {
      const inode = getInode(path);
      if(inode.content !== undefined) {
        openedFiles[path] = inode.content;
      } else {
        const res = await fetch([files_uri.replace(/\/+$/, ''), path].join('/'));
        openedFiles[path] = await res.text();
      }
    }
    current = path;
  }

	async function open(name, inode) {
		if(inode.type == 'dir') {
			path = [...path, name];
    } else {
      openFile([...path, name].join('/'));
		}
  }

  function createDir(e) {
    if(e.keyCode == 13) {
      console.log(path + e.target.value);
      newDirName = false;

      getInode(path)['files'][e.target.value] = {
        'type': 'dir',
        'files': {},
      };
    }
  }

  openFile('readme.md')
  let newDirName = false;

  async function addToUploadQueue(evt) {
    for(const file of evt.target.files) {
      await fetch(files_uri + file.name, {
        method: 'PUT',
        body: file,
      });
    }
  }

  let renamingPath = null;

  let ctxMenu = null;
  function showCtxMenu(e, path) {
    ctxMenu = {
      left: e.pageX,
      top: e.pageY,
      selected: path,
    };
  }

  async function remove(path) {
    await fetch(files_uri + path, {
      method: 'DELETE',
    });

    const parts = path.split('/');
    let root = files;
    for(const dir of parts.slice(0, -1)) {
      root = root[dir]['files'];
    }

    delete root[parts[parts.length - 1]];
    path = path;
  }

  function finishRename(e) {
    if(e.keyCode == 13) {
      console.log(e.target.value, renamingPath);
      renamingPath = null;
    }
  }

  function newFile() {
    let name = 'newfile.txt';
    getInode(path)['files'][name] = {
      type: 'file',
      content: '',
    };
    path = path;
    renamingPath = path + name;

  }

</script>

<div>
  {path.join('/')}/
</div>
<div class="d-flex">
  <div class="tree">
    <div class="action-buttons">
      <span on:click={() => newFile()}>
        <span class="iconify" data-icon="bx:bxs-file-plus"></span>
      </span>
      <span on:click={() => newDirName = ''}>
        <span class="iconify" data-icon="ic:sharp-create-new-folder"></span>
      </span>
      <span>
        <label for="manager-file-upload">
          <span class="iconify" data-icon="ic:sharp-file-upload"></span>
        <label>
        <input id="manager-file-upload" type="file" style="display: none" multiple on:change={addToUploadQueue}>
      </span>
    </div>
    <ul>
      {#if path.length}
      <li on:click={() => path = path.slice(0, -1)}>..</li>
      {/if}
      {#if newDirName !== false}
      <li class="newdir">
          <span class="iconify" data-icon='ic:baseline-folder'></span>
          <input type="text" on:keyup|preventDefault={createDir}>
      </li>
      {/if}
      {#each Object.entries(dirFiles) as [name, inode]}
        <li on:click={open(name, inode)} on:contextmenu|preventDefault={(e) => showCtxMenu(e, [...path, name].join('/'))} style="white-space: nowrap">
          <span class="iconify" data-icon="{inode.type == 'dir' ? 'ic:baseline-folder' : 'ic:outline-insert-drive-file'}"></span>
          {#if renamingPath == path + name}
            <input value={name} on:keyup={finishRename}>
          {:else}
            {name}
          {/if}
        </li>
      {/each}
    </ul>
  </div>
  <div class="w-100">
    <ul class="nav nav-tabs">
      {#each Object.entries(openedFiles) as [path, _]}
      <li class="nav-item" on:click={() => openFile(path)} style="cursor: pointer">
        <span class="nav-link" class:active={path === current}>{path.split('/').slice(-1)[0]}</span>
      </li>
      {/each}
    </ul>

    {#if current}
      <textarea class="form-control" rows=20 bind:value={openedFiles[current]}></textarea>
    {/if}
  </div>
</div>

{#if ctxMenu}
  <div class="dropdown-menu show" style="position: absolute; top: {ctxMenu.top}px; left: {ctxMenu.left}px" use:clickOutside on:click_outside={() => ctxMenu = null}>
    <span class="dropdown-item" on:click={() => {renamingPath = ctxMenu.selected; ctxMenu = null}}><span class="iconify" data-icon="wpf:rename"></span> rename</span>
    <span class="dropdown-item" on:click={() => {remove(ctxMenu.selected); ctxMenu = null}}><span class="iconify" data-icon="wpf:delete"></span> delete</span>
  </div>
{/if}
