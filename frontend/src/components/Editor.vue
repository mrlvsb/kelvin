<script setup lang="ts">
/*
 * Component used to display code mirror editor
 */

import { ref, watch, onUnmounted, defineModel, markRaw, PropType } from 'vue';

import CodeMirror from 'codemirror';
import { lintPipeline } from '../PipelineValidation.js';
import { curTheme as curThemeSvelte } from '../utils.js';
import 'codemirror/lib/codemirror.css';
import 'codemirror/mode/clike/clike.js';
import 'codemirror/mode/yaml/yaml.js';
import 'codemirror/mode/python/python.js';
import 'codemirror/mode/markdown/markdown.js';
import 'codemirror/mode/htmlmixed/htmlmixed.js';
import 'codemirror/addon/display/fullscreen.js';
import 'codemirror/addon/display/fullscreen.css';
import 'codemirror/addon/lint/lint.js';
import 'codemirror/addon/lint/lint.css';
import 'codemirror/addon/hint/show-hint.js';
import 'codemirror/addon/hint/show-hint.css';
import { useReadableSvelteStore } from '../utilities/useSvelteStoreInVue';

/**
 * @prop {string}  filename   - used to determine hints and highlighting from extension, default ''
 * @prop {boolean} autofocus  - enable/disable autofocus on editor, default false
 * @prop {boolean} disabled   - if true then editor is read only, default false
 * @prop {boolean} wrap       - wrap long lines, default false
 * @prop {Record<string, () => void>} extraKeys
 * default keys are:
 *    - Ctrl-Space   autocomplete
 *    - F11          full screen
 *    - ESC          escape full screen
 *    - Tab          soft tab
 *    You can add custom ones in form { 'key': function }
 */
const props = defineProps({
  filename: { type: String, default: '', required: false },
  autofocus: { type: Boolean, default: false, required: false },
  disabled: { type: Boolean, default: false, required: false },
  extraKeys: {
    type: Object as PropType<Record<string, () => void>>,
    default: () => ({}),
    required: false
  },
  wrap: { type: Boolean, default: false, required: false }
});

/**
 * @model
 * @type {string}
 * @description bound variable with editor text content
 */
const modelValue = defineModel<string>();

let curTheme = useReadableSvelteStore<string>(curThemeSvelte);

/**
 * returns MIME type from filename extension
 * @param filename name of file
 */
function toMode(filename: string): string {
  const parts = filename.split('.');
  const ext = parts[parts.length - 1].toLowerCase();
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

/**
 * Convert svelte theme name (light/ dark) to Code Mirror theme
 * @param value svelte theme name
 */
function getTheme(value: string): string {
  return value == 'dark' ? 'dracula' : 'default';
}

let codeMirrorEditor = ref<CodeMirror.EditorFromTextArea | null>(null);
let editorTag = ref<HTMLTextAreaElement | null>(null);

//initialize codemirror once HTML tag is bound to variable
watch(editorTag, (newEditorTag) => {
  if (newEditorTag && !codeMirrorEditor.value) {
    //https://stackoverflow.com/questions/67686617/codemirror-on-vue3-has-a-problem-when-setvalue-is-kicked
    codeMirrorEditor.value = markRaw(
      CodeMirror.fromTextArea(newEditorTag, {
        mode: toMode(props.filename),
        autofocus: props.autofocus,
        lineWrapping: props.wrap,
        gutters: ['CodeMirror-lint-markers'],
        spellcheck: true,
        theme: getTheme(curTheme.value),
        readOnly: props.disabled,
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
          ...props.extraKeys
        }
      })
    );

    if (modelValue.value) codeMirrorEditor.value.setValue(modelValue.value);

    codeMirrorEditor.value.on('change', (doc) => {
      modelValue.value = doc.getValue();
    });
  }
});

function setUpOptions() {
  if (codeMirrorEditor.value) {
    codeMirrorEditor.value.setOption('mode', toMode(props.filename));
    codeMirrorEditor.value.setOption('readOnly', props.disabled);
    codeMirrorEditor.value.setOption(
      'gutters',
      props.filename == '/config.yml' ? ['CodeMirror-lint-markers'] : []
    );

    codeMirrorEditor.value.setOption('lint', props.filename == '/config.yml' ? lintPipeline : null);
    codeMirrorEditor.value.setOption('spellcheck', props.filename != '/config.yml');
    codeMirrorEditor.value.setOption('theme', getTheme(curTheme.value));
  }
}

watch(codeMirrorEditor, setUpOptions);

watch(modelValue, (newVal) => {
  if (codeMirrorEditor.value && codeMirrorEditor.value.getValue() != newVal)
    codeMirrorEditor.value.setValue(newVal);
  setUpOptions();
});

onUnmounted(() => {
  if (codeMirrorEditor.value) {
    codeMirrorEditor.value.toTextArea();
  }
});
</script>

<template>
  <div :class="{ disabled: props.disabled }">
    <textarea ref="editorTag" class="form-control"></textarea>
  </div>
</template>

<style scoped>
:global(.CodeMirror) {
  border: 1px solid #ced4da;
  border-radius: 0.25rem;
  resize: vertical;
}

:global(.disabled > .CodeMirror) {
  background: #eee;
}

:global(.disabled > .CodeMirror .CodeMirror-cursors) {
  display: none;
}
</style>
