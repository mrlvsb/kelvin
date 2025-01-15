import CodeMirror from 'codemirror';

// Remove string Type Union from EditorConfiguration
export type ExtraKeys<$BaseType> = $BaseType extends string ? never : $BaseType;

export type Arrayable<$Type> = $Type | $Type[];

export const inArrayable = <T>(arrayable: Arrayable<T>, value: T) => {
    if (Array.isArray(arrayable)) {
        return arrayable.some((item) => item === value);
    }
    return arrayable === value;
};

export const arrayify = <T>(arrayable: Arrayable<T>) => {
    if (Array.isArray(arrayable)) return arrayable;
    return [arrayable];
};

/**
 * Type definition for extension
 * Each extension is a function. This function can accept these parameters:
 * Extension function is the main code for extension. You can accept these parameters:
 * - fileName - current file filename
 * - code - current code in editor
 * - editor - current editor instance
 * - type - gives you information about context, in which was function called. It can be one of these:
 *   - setup - This is called when editor is created (first time), or filename changed
 *   - lint - This is called when linting is requested (after code change)
 *   - hint - This is called when hinting is requested (after user presses ctrl+space)
 *
 * From this function you can return these things:
 * - Undefined for case, where you don't care about for example current file/extension (extension
 *   for json file doesn't do anything with python file, etc..), empty object is also valid return value
 *   and do same thing as undefined
 * - Object containing these keys:
 *   - spellCheck - Controlls if spellcheck should be enabled/disabled (only for setup)
 *   - gutters - List of gutters to set for current editor (only for setup)
 *   - hint - This will be array of hints, for user to select them
 *   - lint - Lint warning/errors for current code
 * - You don't need to set every key in object, only these, you do care. For example:
 *   - if you only care for hints, return something like this:
 *     ```TS
 *     return {
 *        hint: {
 *            list: ["const", "console"],
 *            from: {
 *               ch: 2,
 *               line: 2
 *            },
 *            to: {
 *                ch: 5,
 *                line: 2
 *            }
 *        }
 *     }
 *     ```
 *   - or if you want to enable spellcheck on setup:
 *     ```TS
 *     return {
 *        spellCheck: true
 *     }
 *     ```
 */
export type EditorExtension = (
    fileName: string,
    code: string,
    editor: CodeMirror.Editor,
    type: 'setup' | 'lint' | 'hint'
) =>
    | undefined
    | {
          spellCheck?: boolean;
          gutters?: string[];
          hint?: CodeMirror.Hint;
          lint?: CodeMirror.LintError[];
      };

export const getExtension = (filename: string) => {
    if (!filename) return;

    const parts = filename.split('.');
    return parts[parts.length - 1].toLowerCase();
};
