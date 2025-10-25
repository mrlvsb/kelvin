import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import pluginVue from 'eslint-plugin-vue';
import ts from 'typescript-eslint';

/** @type {import("eslint").Linter.Config} */
export default [
    js.configs.recommended,
    ...ts.configs.recommended,
    ...pluginVue.configs['flat/recommended'],
    prettier,
    {
        ignores: [
            'node_modules',
            'rollup.config.js',
            'package-lock.json',
            'pnpm-lock.yaml',
            'rollup.config.js'
        ]
    },
    {
        files: ['*.vue', '**/*.vue'],
        languageOptions: {
            parserOptions: {
                parser: '@typescript-eslint/parser'
            }
        },
        rules: {
            'vue/multi-word-component-names': 'off'
        }
    },
    {
        rules: {
            'no-prototype-builtins': 'off'
        }
    }
];
