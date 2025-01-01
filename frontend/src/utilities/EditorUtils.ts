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

// Add more if needed
export type HelperType = 'lint' | 'hint'; // Source: https://snyk.io/advisor/npm-package/codemirror/functions/codemirror.registerHelper
type BaseHelper<$Type extends HelperType, $Callback extends (...args: unknown[]) => unknown> = {
    type: $Type;
    fileType: string;
    callback: $Callback;
};

type HelperFunction<$Helper extends Helper> = (
    returns: (ReturnType<$Helper['callback']> | undefined)[]
) => ReturnType<$Helper['callback']>;

/**
 * Lint Helper, which show error
 * This helper should provide function, which gets two parameters:
 * @param code {string} Current code in editor
 * @param options {unknown} Options
 * @returns this function should return array of errors.
 * Each object contains:
 * - message describing error/warning
 * - severity (optional) error/warning, defaults to error (if gutters
 *   include 'CodeMirror-lint-markers' it will show icons, next to line)
 * - from and to defining start and end of the error
 *
 * @example ```TS
 * function lint(code: string) {
 *     const lines = code.split('\n');
 *     const errors: ReturnType<LintHelper['callback']> = [];
 *
 *     const warningErrors = ['hello', 'javascript'];
 *     const errorErrors = ['galaxy', 'blackhole'];
 *
 *     let lineN = 0;
 *     for (const line of lines) {
 *         const words = line.split(' ');
 *
 *         let char = 0;
 *
 *         for (const word of words) {
 *             if (warningErrors.includes(word)) {
 *                 errors.push({
 *                     message: 'Word ' + word + ' is banned',
 *                     severity: 'warning',
 *                     from: {
 *                         line: lineN,
 *                         ch: char
 *                     },
 *                     to: {
 *                         line: lineN,
 *                         ch: char + word.length
 *                     }
 *                 });
 *             }
 *
 *             if (errorErrors.includes(word)) {
 *                 errors.push({
 *                     message: 'Word ' + word + ' is banned',
 *                     severity: 'error',
 *                     from: {
 *                         line: lineN,
 *                         ch: char
 *                     },
 *                     to: {
 *                         line: lineN,
 *                         ch: char + word.length
 *                     }
 *                 });
 *             }
 *
 *             char += word.length + 1; //newline
 *         }
 *
 *         ++lineN;
 *     }
 *
 *     return errors;
 * }
 * ```
 */
export type LintHelper = BaseHelper<
    'lint',
    (
        code: string,
        options: unknown,
        editor: CodeMirror.Editor
    ) => {
        message: string;
        severity?: 'error' | 'warning';
        from: CodeMirror.Position;
        to: CodeMirror.Position;
    }[]
>;

/**
 * Function, that handles merging of return types from
 * lintHelper, since we can register more lintHelpers for
 * single fileType.
 * @param returns array of return values from lintHelpers. Undefined for helpers, which
 * doesn't satisfy the filename.
 * @returns merged array
 */
const LintHelperMerge = ((returns: (ReturnType<LintHelper['callback']> | undefined)[]) => {
    return returns.filter((ret) => ret !== undefined).reduce((a, b) => a.concat(b), []);
}) satisfies HelperFunction<LintHelper>;

/**
 * Hint Helper, which will show menu with options (syntax)
 * This helper should provide function, which gets two parameters:
 * @param editor {CodeMirror.Editor} CodeMirror Editor instance
 * @param options {unknown} Options
 * @returns this function should return object including:
 * - list of possible items in the list
 * - from and to defining position in editor, which should be replaced by the selected word
 *
 * @example ```TS
 * function hint(editor: CodeMirror.Editor) {
 *     const cursor = editor.getCursor();
 *     const token = editor.getTokenAt(cursor);
 *     return {
 *       list: ['first', 'last'], //words
 *       from: {
 *         ch: token.start,
 *         line: cursor.line
 *       },
 *       to: {
 *         ch: token.end,
 *         line: cursor.line
 *       }
 *     };
 * }
 * ```
 */
export type HintHelper = BaseHelper<
    'hint',
    (
        editor: CodeMirror.Editor,
        options: unknown
    ) => {
        list: string[];
        from: CodeMirror.Position;
        to: CodeMirror.Position;
    }
>;

/**
 * Function, that handles merging of return types from
 * hintHelper, since we can register more hintHelpers for
 * single fileType.
 * @param returns array of return values from hintHelpers. Undefined for helpers, which
 * doesn't satisfy the filename.
 * @returns merged array
 */
const HintHelperMerge = ((returns: (ReturnType<HintHelper['callback']> | undefined)[]) => {
    const filtered = returns.filter((ret) => ret !== undefined);
    return {
        list: filtered.map((item) => item.list).reduce((a, b) => a.concat(b), []),
        from: filtered[0].from,
        to: filtered[0].to
    };
}) satisfies HelperFunction<HintHelper>;

/**
 * Helper for CodeMirror
 * @example
 * ```TS
 * const hint = ((editor: CodeMirror.Editor) => {
 *     const cursor = editor.getCursor();
 *     const token = editor.getTokenAt(cursor);
 *     return {
 *       list: ['first', 'last'], //words
 *       from: {
 *         ch: token.start,
 *         line: cursor.line
 *       },
 *       to: {
 *         ch: token.end,
 *         line: cursor.line
 *       }
 *     };
 * }) satisfies HintHelper
 * ```
 */
export type Helper = LintHelper | HintHelper;
export const HelperMergers: Record<Helper['type'], HelperFunction<Helper>> = {
    lint: LintHelperMerge,
    hint: HintHelperMerge
} as const;

/**
 * Define extension for exitor
 * Each extension, can have condition for fileName(s) or file extension(s),
 * then it can set gutters, helpers and spellCheck option for the condition.
 * @example Sample extension for ./config.yml/yaml file, adding lint markers
 * \+ added PipeLinehelper for hinting.
 * ```TS
 * const yamlExtension = {
 *     fileName: ["./config.yml", "./config.yaml"],
 *     gutters: "CodeMirror-lint-markers",
 *     helpers: PipeLineHelper
 * } satisfies EditorExtension;
 * ```
 *
 * @example Sample JS extension for js file adding spellcheck.
 * ```TS
 * const jsExtension = {
 *     extension: "js",
 *     spellCheck: true
 * } satisfies EditorExtension;
 * ```
 */
export type EditorExtension = {
    fileName?: string | string[];
    extension?: string | string[];
    gutters?: string | string[];
    helpers?: Helper | Helper[];
    spellCheck?: boolean;
};

export const getExtension = (filename: string) => {
    if (!filename) return;

    const parts = filename.split('.');
    return parts[parts.length - 1].toLowerCase();
};

//append extensions to editor, for current file
export const appendExtensions = (
    editor: CodeMirror.Editor,
    extensions: EditorExtension[],
    filename: string
) => {
    const fileExt = getExtension(filename);

    const gutters: string[] = [];
    let spellcheck = false;

    for (const extension of extensions) {
        let include = false;

        if (extension.fileName !== undefined) {
            include = inArrayable(extension.fileName, filename);
        } else if (extension.extension !== undefined) {
            include = inArrayable(extension.extension, fileExt);
        }

        if (!include) continue; //skip

        if (extension.spellCheck !== undefined) spellcheck = spellcheck || extension.spellCheck;

        if (extension.gutters) gutters.push(...arrayify(extension.gutters));
    }

    editor.setOption('gutters', gutters);
    editor.setOption('lint', true);
    editor.setOption('spellcheck', spellcheck);
};

//append helpers to CodeMirror
export const appendHelpers = (extensions: EditorExtension[]) => {
    //group helpers together, to register them at once
    type HelperCallback = Helper['callback'];

    const groupedhelper: {
        type: HelperType;
        helpers: Record<string, HelperCallback[]>;
    }[] = [];

    for (const extension of extensions) {
        if (!extension.helpers) continue;

        const createWrapperFunction = (func: HelperCallback) => {
            const extractEditor = (args: Parameters<HelperCallback>): CodeMirror.Editor => {
                if (args[0] instanceof CodeMirror) return args[0];
                return args[2];
            };

            if (extension.fileName) {
                const fileNames = arrayify(extension.fileName);

                return (...args: Parameters<HelperCallback>) => {
                    const editor = extractEditor(args);
                    const fileName = editor.getOption('filename');
                    if (!fileNames.includes(fileName)) return;

                    // eslint-disable-next-line prefer-spread
                    return func.apply(null, args);
                };
            } else if (extension.extension) {
                const extensions = arrayify(extension.extension);

                return (...args: Parameters<HelperCallback>) => {
                    const editor = extractEditor(args);
                    const fileName = editor.getOption('filename');
                    const extension = getExtension(fileName);

                    if (!extensions.includes(extension)) return;

                    // eslint-disable-next-line prefer-spread
                    return func.apply(null, args);
                };
            }
        };

        let helpers: Helper[];

        if (Array.isArray(extension.helpers)) {
            helpers = extension.helpers;
        } else {
            helpers = [extension.helpers];
        }

        for (const helper of helpers) {
            let index: number;
            if (!groupedhelper.map((helper) => helper.type).includes(helper.type)) {
                index = groupedhelper.push({ type: helper.type, helpers: {} }) - 1;
            } else {
                index = groupedhelper.findIndex((group) => group.type === helper.type);
            }

            const group = groupedhelper[index];

            if (!(helper.fileType in group.helpers)) {
                group.helpers[helper.fileType] = [];
            }

            group.helpers[helper.fileType].push(createWrapperFunction(helper.callback));
        }
    }

    for (const group of groupedhelper) {
        const helperMerger = HelperMergers[group.type];

        for (const [fileType, callbacks] of Object.entries(group.helpers)) {
            CodeMirror.registerHelper(group.type, fileType, (...args: unknown[]) => {
                const returns = callbacks.map((cb) => cb.apply(this, args));
                return helperMerger(returns);
            });
        }
    }
};
