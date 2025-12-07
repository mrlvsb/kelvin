<script setup lang="ts">
/**
 * FileManager Component
 *
 * Displays a list of files in a left panel and editor.
 * Users can:
 * - Rename files
 * - Create new directories
 * - Upload files
 * - Open configuration files
 * - Open tests tab
 *
 * Opened files are displayed as tabs above the editor.
 */

import { ref, watch, triggerRef } from 'vue';
import { fetch } from '../../api';
import {
  useReadableSvelteStore,
  useWritableSvelteStore
} from '../../utilities/useSvelteStoreInVue';
import { clickOutside } from '../../utilities/clickOutside';
import Editor from '../../components/Editor.vue';
import { FileEntry } from '../../utilities/SvelteStoreTypes';
import Tests from './Tests.vue';
import {
  currentOpenedFile as currentOpenedFileSvelte,
  fs,
  currentPath as currentPathSvelte,
  cwd as cwdSvelte,
  openedFiles as openedFilesSvelte
} from '../../fs';

/**
 * @prop {Number} taskid - current task id, for reevaluate button in config.yml file
 */
let { taskid } = defineProps<{
  taskid: number;
}>();

/**
 * file list panel context menu position
 */
interface ContextMenu {
  left: number;
  top: number;
  selected: string;
}

const vClickOutside = clickOutside;

const currentPath = useReadableSvelteStore<string>(currentPathSvelte);
const cwd = useReadableSvelteStore<FileEntry[]>(cwdSvelte);
const currentOpenedFile = useWritableSvelteStore<string | null>(currentOpenedFileSvelte);
const openedFiles = useWritableSvelteStore<Record<string, FileEntry>>(openedFilesSvelte);

let renamingPath = ref<string | null>(null);
let ctxMenu = ref<ContextMenu | null>(null);
let newDirName = ref<string | boolean>(false);
let testsActivated = ref<boolean>(false);

watch(renamingPath, (newVal) => console.log(newVal));

/**
 * renames the file in the left pane if the Enter key is pressed during editing
 */
function finishRename(e: KeyboardEvent): void {
  if (e.key == 'Enter') {
    let input: HTMLInputElement = e.target as HTMLInputElement;
    fs.rename(renamingPath.value, input.value);
    renamingPath.value = null;
  }
}

/**
 * Show context menu on left click in file list
 */
function showCtxMenu(e: MouseEvent, path: string): void {
  ctxMenu.value = {
    left: e.pageX,
    top: e.pageY,
    selected: currentPath.value + '/' + path
  };
}

/**
 * Delete file/dir in specified path
 */
async function remove(path: string): Promise<void> {
  await fs.remove(path);
}

function createDir(e: KeyboardEvent): void {
  if (e.key == 'Enter') {
    newDirName.value = false;
    let input: HTMLInputElement = e.target as HTMLInputElement;
    fs.mkdir(input.value);
  }
}

async function addToUploadQueue(e: Event): Promise<void> {
  let input: HTMLInputElement = e.target as HTMLInputElement;

  if (!input.files) return;

  for (const file of input.files) {
    await fs.upload(file.name, file);
  }
}

/**
 * It will attempt to open the YAML configuration file;
 * if it does not exist, it will create a new one with the default configuration.
 */
async function openConfigYaml(): Promise<void> {
  const fileName = '/config.yml';

  if (!(await fs.open(fileName))) {
    fs.createFile(
      fileName,
      `
# https://mrlvsb.github.io/kelvin/teachers-guide/task-configuration/pipeline
# You can also use CTRL+Space for autocompleting
pipeline:
  # compile submitted source codes
  - type: gcc
  # flags: -Wall -Wextra -g -fsanitize=address -lm -Wno-unused-variable

  # add hints from clang-tidy as comments
  #- type: clang-tidy

  # run tests
  #- type: tests

  # run custom commands
  #- type: run
  #  commands:
  #    - ./main 123 | wc -l

  # automatically assign points from the test results
  #- type: auto_grader

`.trim()
    );

    await fs.open(fileName);
  }
}

async function reevaluate() {
  await fetch(`/api/reevaluate_task/${taskid}`, { method: 'POST' });
}

/**
 * Shows tests tab
 */
function openTests() {
  testsActivated.value = true;
  currentOpenedFile.value = null;
}

function closeTab(path: string) {
  fs.close(path);
  triggerRef(openedFiles);
}
</script>

<template>
  <div>
    {{ currentPath }}
  </div>
  <div class="d-flex">
    <div class="tree">
      <div class="action-buttons">
        <span @click="renamingPath = '/' + fs.createFile('newfile.txt')">
          <span class="iconify" data-icon="bx:bxs-file-plus"></span>
        </span>
        <span @click="newDirName = ''">
          <span class="iconify" data-icon="ic:sharp-create-new-folder"></span>
        </span>
        <span>
          <input
            id="manager-file-upload"
            type="file"
            style="display: none"
            multiple
            @click="
              (e) => {
                let input: HTMLInputElement = e.target as HTMLInputElement;
                input.value = null;
              }
            "
            @change="addToUploadQueue"
          />
          <label for="manager-file-upload">
            <span class="iconify" data-icon="ic:sharp-file-upload"></span>
          </label>
        </span>
        <span @click="openConfigYaml">
          <span class="iconify" data-icon="vscode-icons:file-type-light-config"></span>
        </span>
        <span @click="openTests">
          <span class="iconify" data-icon="fa6-solid:t"></span>
        </span>
      </div>
      <ul>
        <li v-if="currentPath !== '/'" @click="currentPathSvelte.up()">
          <span class="iconify" data-icon="ic:baseline-folder"></span>
          ..
        </li>
        <li v-if="newDirName !== false" class="newdir">
          <span class="iconify" data-icon="ic:baseline-folder"></span>
          <input type="text" autofocus @keyup.prevent="createDir" />
        </li>
        <li
          v-for="inode in cwd"
          :key="inode.name"
          style="white-space: nowrap"
          @contextmenu.prevent="(e) => showCtxMenu(e, inode.name)"
        >
          <span
            class="iconify"
            :data-icon="inode.type == 'dir' ? 'ic:baseline-folder' : 'ic:outline-insert-drive-file'"
          ></span>
          <input
            v-if="renamingPath === currentPath + '/' + inode.name"
            :value="inode.name"
            autofocus
            @keyup="finishRename"
          />
          <span v-else @click="fs.open(inode.name)">{{ inode.name }}</span>
        </li>
      </ul>
    </div>
    <div class="w-100" style="overflow: hidden">
      <ul class="nav nav-tabs">
        <li v-if="testsActivated" class="nav-item" style="cursor: pointer">
          <span class="nav-link" :class="{ active: !currentOpenedFile }">
            <span @click="openTests">Tests</span>
          </span>
        </li>

        <li
          v-for="path in Object.keys(openedFiles).filter((key) => !openedFiles[key].hide_tab)"
          :key="path"
          class="nav-item"
          style="cursor: pointer"
        >
          <span class="nav-link" :class="{ active: path === currentOpenedFile }">
            <span @click="currentOpenedFile = path">{{ path.split('/').slice(-1)[0] }}</span>
            <span @click="closeTab(path)"> <span class="iconify" data-icon="fa:times"></span></span>
          </span>
        </li>
      </ul>

      <div class="editor-container">
        <div
          v-if="currentOpenedFile === '/config.yml'"
          style="position: absolute; z-index: 3; right: 5px"
        >
          <button class="btn btn-link p-0" title="Reevaluate all submits" @click="reevaluate">
            <span class="iconify" data-icon="bx:bx-refresh"></span>
          </button>
          <a
            href="https://mrlvsb.github.io/kelvin/teachers-guide/task-configuration/pipeline"
            target="_blank"
          >
            <span class="iconify" data-icon="entypo:help"></span>
          </a>
        </div>

        <div :hidden="currentOpenedFile != null">
          <Tests />
        </div>

        <Editor
          v-if="currentOpenedFile"
          v-model="openedFiles[currentOpenedFile].content"
          :filename="currentOpenedFile"
        />
      </div>
    </div>
  </div>

  <div
    v-if="ctxMenu && ctxMenu.selected != '/readme.md'"
    class="dropdown-menu show"
    v-click-outside="() => (ctxMenu = null)"
    :style="{ position: 'fixed', top: ctxMenu.top + 'px', left: ctxMenu.left + 'px' }"
  >
    <button
      class="dropdown-item"
      @click.prevent="
        () => {
          renamingPath = ctxMenu.selected;
          ctxMenu = null;
        }
      "
    >
      <span class="iconify" data-icon="wpf:rename"></span> rename
    </button>
    <button
      class="dropdown-item"
      @click.prevent="
        () => {
          remove(ctxMenu.selected);
          ctxMenu = null;
        }
      "
    >
      <span class="iconify" data-icon="wpf:delete"></span> delete
    </button>
  </div>
</template>

<style scoped>
.tree {
  width: 200px;
}

.tree ul {
  list-style: none;
  padding: 0;
}

.tree ul li {
  cursor: pointer;
  overflow-x: hidden;
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

:global(.editor-container .CodeMirror) {
  border-top: 0;
  min-height: 600px;
}
</style>
