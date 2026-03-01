<script setup lang="ts">
/**
 * This component is used as Editor for editing file content.
 * It provides interface for adding Extensions, which
 * can for example add custom linting or hinting.
 */

import CodeMirror, { EditorFromTextArea, type EditorConfiguration } from 'codemirror';
import { markRaw, ref, watch, onUnmounted } from 'vue';
import { theme, ThemeValue } from '../utilities/theme';
import { EditorExtension, ExtraKeys } from '../utilities/EditorUtils';
import { getExtension } from '../utilities/EditorUtils';
import { lintPipeline } from '../PipelineValidation.js';

const editorContent = defineModel<string>();

let {
  autofocus = false,
  disabled = false,
  extraKeys = {},
  wrap = false,
  extensions = [],
  lint = false,
  filename,
  spellcheck = true
} = defineProps<{
  /**
   * Autofocus editor on mount
   * Defaults to false
   */
  autofocus?: boolean;
  /**
   * Disables the editor (readonly)
   * Defaults to false
   */
  disabled?: boolean;
  /**
   * Define new key-combinations for editor
   * It is object, where key is key-combination and value is function
   * which will be executed when user presses this key-combination
   * Defaults to empty object
   */
  extraKeys?: ExtraKeys<EditorConfiguration['extraKeys']>;
  /**
   * Whether CodeMirror should scroll or wrap for long lines.
   * Defaults to false (scroll).
   */
  wrap?: boolean;
  /**
   *List of extensions which will be used in editor
   */
  extensions?: EditorExtension[];
  /**
   * Whether to perform linting or not. Defaults to false
   * If no extension is provided, this option will do nothing
   * Defaults to false
   */
  lint?: boolean;
  filename: string;
  /**
   * Should you browser spellcheck the content?
   * Defaults to true
   */
  spellcheck?: boolean;
}>();

let editorElement = ref();
let editor: EditorFromTextArea;

function getThemeName(value: ThemeValue) {
  return value == 'dark' ? 'dracula' : 'default';
}

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

const handleHint = (editor: CodeMirror.Editor) => {
  for (const extension of extensions) {
    const result = extension(filename, editorContent.value, editor, 'hint');
    if (!result) continue;

    if (result.hint) {
      CodeMirror.showHint(editor, () => result.hint);
    }
  }
};

const handleLint = (code: string, _: unknown, editor: CodeMirror.Editor) => {
  const lints: CodeMirror.LintError[] = [];

  for (const extension of extensions) {
    const result = extension(filename, code, editor, 'lint');
    if (!result) continue;

    if (result.lint) {
      lints.push(...result.lint);
    }
  }

  return lints;
};

const handleSetup = (editor: CodeMirror.Editor) => {
  const gutters: string[] = [];

  for (const extension of extensions) {
    const result = extension(filename, editorContent.value, editor, 'setup');

    if (!result) continue;

    if (result.gutters) {
      gutters.push(...result.gutters);
    }

    if (result.spellCheck !== undefined) {
      editor.setOption('spellcheck', result.spellCheck);
    }
  }

  editor.setOption('gutters', gutters);
  editor.refresh();
};

const DEFAULT_KEY_MAP = {
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
  }
} satisfies ExtraKeys<EditorConfiguration['extraKeys']>;

function setUpOptions() {
  if (editor) {
    editor.setOption('filename', filename);
    editor.setOption('lint', filename == '/config.yml' ? lintPipeline : lint ? handleLint : false);
    editor.setOption('mode', toMode(filename));
    editor.setOption('readOnly', disabled);
    editor.setOption('extraKeys', {
      'Ctrl-Space': filename == '/config.yml' ? 'autocomplete' : handleHint,
      ...DEFAULT_KEY_MAP,
      ...extraKeys
    });
  }
}

//initialize editor
const initializeEditor = () => {
  //https://stackoverflow.com/questions/67686617/codemirror-on-vue3-has-a-problem-when-setvalue-is-kicked
  editor = markRaw(
    CodeMirror.fromTextArea(editorElement.value, {
      autofocus,
      lineWrapping: wrap,
      gutters: ['CodeMirror-lint-markers'],
      spellcheck,
      theme: getThemeName(theme.value),
      inputStyle: 'contenteditable',
      tabSize: 2
    })
  );

  //call setup first time, because editor is initialized
  handleSetup(editor);

  editor.on('change', (editor) => {
    editorContent.value = editor.getValue();
  });

  if (editorContent.value) editor.setValue(editorContent.value);

  setUpOptions();
};

//onMounted(initializeEditor);

watch(editorElement, (newEditorTag) => {
  if (newEditorTag && !editor) {
    initializeEditor();
  }
});

//update editor based on value in model
watch(editorContent, (value) => {
  if (value != editor.getValue()) {
    editor.setValue(value);
    setUpOptions();
  }
});

//because props are not ref, we need to wrap them into getter functions to be reactive
watch(
  [theme, () => autofocus, () => disabled, () => extraKeys],
  ([theme, autofocus, disabled, extraKeys]) => {
    editor.setOption('theme', getThemeName(theme));
    editor.setOption('autofocus', autofocus);
    editor.setOption('readOnly', disabled);
    editor.setOption('extraKeys', {
      ...DEFAULT_KEY_MAP,
      ...extraKeys
    });
  }
);

onUnmounted(() => {
  if (editor) {
    editor.toTextArea();
    //editor = null;
    editorElement.value = '';
  }
});
</script>

<template>
  <div :class="{ disabled: disabled }">
    <textarea ref="editorElement" class="form-control"></textarea>
  </div>
</template>

<style global>
.CodeMirror {
  border: 1px solid #ced4da;
  border-radius: 0.25rem;
  resize: vertical;
}
</style>
