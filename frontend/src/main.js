import 'bootstrap/dist/css/bootstrap.css';
import 'bootstrap/js/dist/collapse';
import './global.css';
import './global.scss';

import hljs from 'highlight.js/lib/core';
import bash from 'highlight.js/lib/languages/bash';
import c from 'highlight.js/lib/languages/c';
import cpp from 'highlight.js/lib/languages/cpp';
import csharp from 'highlight.js/lib/languages/csharp';
import java from 'highlight.js/lib/languages/java';
import makefile from 'highlight.js/lib/languages/makefile';
import python from 'highlight.js/lib/languages/python';
import rust from 'highlight.js/lib/languages/rust';
import shell from 'highlight.js/lib/languages/shell';
import x86asm from 'highlight.js/lib/languages/x86asm';
import xml from 'highlight.js/lib/languages/xml';

hljs.registerLanguage('c-like', cpp);
hljs.registerLanguage('c', c);
hljs.registerLanguage('cpp', cpp);
hljs.registerLanguage('csharp', csharp);
hljs.registerLanguage('java', java);
hljs.registerLanguage('python', python);
hljs.registerLanguage('xml', xml);
hljs.registerLanguage('bash', bash);
hljs.registerLanguage('shell-session', shell);
hljs.registerLanguage('makefile', makefile);
hljs.registerLanguage('assembler', x86asm);
hljs.registerLanguage('asm', x86asm);
hljs.registerLanguage('x86asm', x86asm);
hljs.registerLanguage('rust', rust);
hljs.highlightAll();

import * as Diff2Html from 'diff2html';
import 'diff2html/bundles/css/diff2html.min.css';
window.Diff2Html = Diff2Html;

// Import iconify icons used in UI, don't remove this line (almost forgot to put it back)
import '@iconify/iconify';
import AnsiUp from 'ansi_up';
import App from './App.svelte';
import ColorTheme from './ColorTheme.svelte';
import { safeMarkdown } from './markdown.js';
import PipelineStatus from './PipelineStatus.svelte';

class ReplaceHtmlElement extends HTMLElement {
    constructor() {
        super();
        this.attachShadow({ mode: 'open' });
        this.shadowRoot.innerHTML = '<slot></slot>';
        this.shadowRoot.querySelector('slot').addEventListener(
            'slotchange',
            () => {
                this.onConnect();
                this.style.display = 'block';
            },
            { once: true }
        );
    }
    connectedCallback() {
        this.style.display = 'none';
    }
}

customElements.define(
    'kelvin-terminal-output',
    class extends ReplaceHtmlElement {
        onConnect() {
            const res = new AnsiUp().ansi_to_html(this.innerText);
            this.innerHTML = '<pre>' + res + '</pre>';
        }
    }
);

customElements.define(
    'kelvin-markdown',
    class extends ReplaceHtmlElement {
        onConnect() {
            this.innerHTML = safeMarkdown(this.innerText, { breaks: false });
            this.removeAttribute('hidden');
            this.classList.add('md');
        }
    }
);

function createElement(name, component) {
    customElements.define(
        'kelvin-' + name,
        class extends HTMLElement {
            connectedCallback() {
                let attrs = {};
                for (let i = 0; i < this.attributes.length; i++) {
                    let attr = this.attributes[i];
                    let name = attr.name.replace('-', '_');
                    if (attr.value[0] == '{' || attr.value[0] == '[') {
                        attrs[name] = JSON.parse(attr.value);
                    } else {
                        attrs[name] = attr.value;
                    }
                }

                new component({
                    target: this,
                    props: attrs
                });
            }
        }
    );
}

const getCookies = () => {
    return Object.fromEntries(document.cookie.split('; ').map((cookie) => cookie.split('=')));
};

const cookies = getCookies();
const enableNewUI = Object.keys(cookies).includes('newUI') && cookies['newUI'] != 0;

createElement('app', App);
createElement('pipeline-status', PipelineStatus);

if (!enableNewUI) createElement('color-theme', ColorTheme);

function focusTab() {
    const hash = document.location.hash.replace('#', '').split('-')[0].split(';')[0];
    const link = document.querySelector(`[data-toggle="tab"][href="#${hash}"]`);
    if (!link) {
        return;
    }

    link.closest('ul')
        .querySelectorAll('.nav-link')
        .forEach((el) => el.classList.remove('active'));
    link.classList.add('active');

    document
        .querySelectorAll('.tab-content .tab-pane')
        .forEach((el) => el.classList.remove('active'));

    document.querySelector('#tab_' + hash).classList.add('active');
}

window.addEventListener('hashchange', focusTab);
window.addEventListener('DOMContentLoaded', focusTab);

import { createApp, defineCustomElement, h } from 'vue';
import SuspensionWrapper from './components/SuspensionWrapper.vue';
import TaskList from './Teacher/TaskList.vue';
import InbusImport from './Teacher/InbusImport.vue';
import NotificationsNew from './components/Notifications.vue';
import Toast from './components/Toast.vue';
import ColorThemeNew from './components/ColorTheme.vue';
import UploadSolution from './components/UploadSolution.vue';
import StudentList from './Teacher/StudentList.vue';
import StudentPage from './Teacher/student-page/StudentPage.vue';
import StudentTransfer from './Teacher/StudentTransfer.vue';
import Quiz from './Quiz/Quiz.vue';
import QuizEdit from './Quiz/QuizEdit.vue';
import QuizList from './Quiz/Lists/QuizList.vue';
import QuizSubmitList from './Quiz/Lists/QuizSubmitList.vue';
import MarkButton from './components/MarkButton.vue';
import TaskDetail from './Student/TaskDetail.vue';
import SyncLoader from './components/SyncLoader.vue';

/**
 * Register new Vue component as a custom element.
 * @param {string} name Suffix to `kelvin-` as name of new custom element
 * @param {(props: unknown, ctx: unknown) => unknown} component Vue Component
 * @param {(app: import('@vue/runtime-dom').App) => void} configureApp Expose app variable to use plugins for example
 */
const registerVueComponent = (name, component, configureApp = undefined) => {
    customElements.define(
        `kelvin-${name}`,
        defineCustomElement(component, {
            shadowRoot: false, // https://github.com/vuejs/core/issues/4314#issuecomment-2266382877
            configureApp
        })
    );
};

/**
 * Wrap Vue component in SuspensionWrapper to support toplevel await - https://vuejs.org/guide/built-ins/suspense
 * @param {string} name Suffix to `kelvin-` as name of new custom element
 * @param {(props: unknown, ctx: unknown) => unknown} component Vue Component
 * @param {(app: import('@vue/runtime-dom').App) => void} configureApp Expose app variable to use plugins for example
 */
const registerSuspendedVueComponent = (name, component, configureApp = undefined) => {
    registerVueComponent(
        name,
        {
            render() {
                return h(SuspensionWrapper, { childComponent: component });
            }
        },
        configureApp
    );
};

registerSuspendedVueComponent('task-list', TaskList);
registerVueComponent('student-list', StudentList);
registerSuspendedVueComponent('student-transfer', StudentTransfer);
registerSuspendedVueComponent('inbus-import', InbusImport);
registerVueComponent('notifications', NotificationsNew);
registerVueComponent('toast', Toast);
registerVueComponent('submit-sources', TaskDetail);
registerVueComponent('upload-solution', UploadSolution);
registerVueComponent('quiz', Quiz);
registerVueComponent('quiz-edit', QuizEdit);
registerSuspendedVueComponent('quiz-list', QuizList);
registerSuspendedVueComponent('quiz-submit-list', QuizSubmitList);
if (enableNewUI) registerVueComponent('color-theme', ColorThemeNew);

// TODO: Remove when all Svelte is converted. This will then not needed as custom components.
registerVueComponent('sync-loader', SyncLoader);

// Function that can be used outside the compiled JavaScript
// to mount the student page with the passed props.
function mountStudentPage(id, props) {
    const app = createApp(StudentPage, props);
    app.mount(id);
}

function mountQuiz(id, props) {
    const app = createApp(Quiz, props);
    app.mount(id);
}

function mountQuizEdit(id, props) {
    const app = createApp(QuizEdit, props);
    app.mount(id);
}

function mountMarkButton(id, props) {
    const app = createApp(MarkButton, props);
    app.mount(id);
}

window.mountStudentPage = mountStudentPage;
window.mountQuiz = mountQuiz;
window.mountQuizEdit = mountQuizEdit;
window.mountMarkButton = mountMarkButton;
