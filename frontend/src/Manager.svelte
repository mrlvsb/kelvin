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

.nav-item span {
  padding: 3px 6px;
}
</style>

<script>
  import {clickOutside} from './utils.js';
  import {fetch} from './api.js'
  import {fs, currentPath, cwd, openedFiles, currentOpenedFile} from './fs.js'
  import Editor from './Editor.svelte'

  let renamingPath = null;
  let ctxMenu = null;
  let newDirName = false;

  function newFile() {
    let name = 'newfile.txt';
    renamingPath = fs.createFile('newfile.txt');
  }

  function finishRename(e) {
    if(e.keyCode == 13) {
      fs.rename(renamingPath, e.target.value);
      renamingPath = null;
    }
  }

  function showCtxMenu(e, path) {
    ctxMenu = {
      left: e.pageX,
      top: e.pageY,
      selected: $currentPath + '/' + path,
    };
  }

  async function remove(path) {
    await fs.remove(path);
  }

  function createDir(e) {
    if(e.keyCode == 13) {
      newDirName = false;
      fs.mkdir(e.target.value);
    }
  }

  async function addToUploadQueue(evt) {
    for(const file of evt.target.files) {
      await fs.upload(file.name, file);
    }
  }
</script>

<div>
  {$currentPath}
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
      {#if $currentPath != '/'}
        <li on:click={() => currentPath.up()}>
          <span class="iconify" data-icon="ic:baseline-folder"></span>
          ..
        </li>
      {/if}
      {#if newDirName !== false}
      <li class="newdir">
          <span class="iconify" data-icon='ic:baseline-folder'></span>
          <input type="text" on:keyup|preventDefault={createDir} autofocus>
      </li>
      {/if}
      {#each $cwd as inode (inode)}
        <li on:contextmenu|preventDefault={(e) => showCtxMenu(e, inode.name)} style="white-space: nowrap">
          <span class="iconify" data-icon="{inode.type == 'dir' ? 'ic:baseline-folder' : 'ic:outline-insert-drive-file'}"></span>
          {#if renamingPath == $currentPath + '/' + inode.name}
            <input value={inode.name} on:keyup={finishRename} autofocus>
          {:else}
            <span on:click={() => fs.open(inode.name)}>{inode.name}</span>
          {/if}
          </li>
      {/each}
    </ul>
  </div>
  <div class="w-100">
    <ul class="nav nav-tabs">
      {#each Object.entries($openedFiles) as [path, file]}
      <li class="nav-item" on:click={() => fs.open(path)} style="cursor: pointer">
        <span class="nav-link" class:active={path === $currentOpenedFile}>{path.split('/').slice(-1)[0]}</span>
      </li>
      {/each}
    </ul>

    {#if $currentOpenedFile}
      <Editor filename={$currentOpenedFile} bind:value={$openedFiles[$currentOpenedFile].content} />
    {/if}
  </div>
</div>

{#if ctxMenu && ctxMenu.selected != '/readme.md'}
  <div class="dropdown-menu show" style="position: absolute; top: {ctxMenu.top}px; left: {ctxMenu.left}px" use:clickOutside on:click_outside={() => ctxMenu = null}>
    <span class="dropdown-item" on:click={() => {renamingPath = ctxMenu.selected; ctxMenu = null}}><span class="iconify" data-icon="wpf:rename"></span> rename</span>
    <span class="dropdown-item" on:click={() => {remove(ctxMenu.selected); ctxMenu = null}}><span class="iconify" data-icon="wpf:delete"></span> delete</span>
  </div>
{/if}
