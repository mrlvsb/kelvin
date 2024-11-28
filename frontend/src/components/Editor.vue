<script setup lang="ts">
/**
 * This component is used as Editor for editing file content.
 * It provides interface for adding Extensions, which
 * can for example add custom linting or hinting.
 * Currently it is nowhere available, since integration
 * would need to rewrite much more components.
 */

import CodeMirror, { EditorFromTextArea, type EditorConfiguration } from 'codemirror';
import { ref, watch } from 'vue';
import { currentTheme, ThemeValue } from '../utilities/storage';
import {
  appendExtensions,
  appendHelpers,
  EditorExtension,
  ExtraKeys
} from '../utilities/EditorUtils';
import { getExtension } from '../utilities/EditorUtils';

const editorContent = defineModel<string>('value');

const filename = defineModel<string>('filename', {
  default: ''
});

let {
  autofocus = false,
  disabled = false,
  extraKeys = {},
  wrap = false,
  extensions = [],
  lint = false
} = defineProps<{
  autofocus?: boolean;
  disabled?: boolean;
  extraKeys?: ExtraKeys<EditorConfiguration['extraKeys']>;
  wrap?: boolean;
  extensions?: EditorExtension[];
  lint?: boolean;
}>();

function getTheme(value: ThemeValue) {
  return value == 'dark' ? 'dracula' : 'default';
}

let editorElement = ref();
let editor: EditorFromTextArea;

function toMode(filename: string) {
  const ext = getExtension(filename);
  const map = {
    c: 'text/x-csrc',
    h: 'text/x-csrc',
    cpp: 'text/x-c++src',
    md: 'markdown',
    yml: 'yaml',
    yaml: 'yaml',
    py: 'python',
    htm: 'htmlmixed',
    html: 'htmlmixed'
  };
  return map[ext];
}

watch(editorElement, () => {
  if (editor) return; // if editor is already initialized

  editor = CodeMirror.fromTextArea(editorElement.value, {
    mode: toMode(filename.value),
    filename: filename.value,
    autofocus,
    lint,
    lineWrapping: wrap,
    gutters: ['CodeMirror-lint-markers'],
    spellcheck: true,
    theme: getTheme(currentTheme.value),
    inputStyle: 'contenteditable',
    readOnly: disabled,
    tabSize: 2,
    extraKeys: {
      'Ctrl-Space': 'autocomplete',
      F11: function (cm) {
        cm.setOption('fullScreen', !cm.getOption('fullScreen'));
      },
      Esc: function (cm) {
        if (cm.getOption('fullScreen')) {
          cm.setOption('fullScreen', false);
        }
      },
      Tab: function (cm) {
        cm.execCommand('insertSoftTab');
      },
      ...extraKeys
    }
  });

  editor.on('change', (editor) => {
    editorContent.value = editor.getValue();
  });

  let timer: number | undefined;

  const observer = new MutationObserver(() => {
    if (timer) {
      clearTimeout(timer);
    }

    timer = setTimeout(() => editor.refresh(), 100);
  });
  observer.observe(document.querySelector('.CodeMirror'), {
    attributes: true
  });

  appendHelpers(extensions);

  //start watching after editor is initialized
  watch(
    [filename, currentTheme],
    ([fName, theme]: [string, ThemeValue]) => {
      if (!editor) return;

      if (theme) {
        editor.setOption('theme', getTheme(theme));
      }

      if (extensions && !fName) {
        fName = filename.value;
      }

      if (fName !== undefined) {
        editor.setOption('mode', toMode(fName));
        editor.setOption('readOnly', disabled);

        appendExtensions(editor, extensions, fName);

        //if linting is enable, toggle it to force lint
        if (editor.getOption('lint')) {
          editor.setOption('lint', false);
          editor.setOption('lint', true);
        }
      }
    },
    {
      immediate: true
    }
  );
});

watch(editorContent, (value) => {
  if (value != editor.getValue()) {
    editor.setValue(value);
  }
});
</script>

<template>
  <div class="">
    <textarea ref="editorElement" class="form-control" :value="editorContent"></textarea>
  </div>
</template>

<style global>
.CodeMirror {
  border: 1px solid #ced4da;
  border-radius: 0.25rem;
  resize: vertical;
}

.disabled > .CodeMirror {
  background: #eee;
}

.disabled > .CodeMirror .CodeMirror-cursors {
  display: none;
}
</style>
