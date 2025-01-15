import CodeMirror from 'codemirror';

declare module 'codemirror' {
    type LintError = {
        severity: 'warning' | 'error';
        message: string;
        from: Position;
        to: Position;
    };

    type Hint = {
        list: string[];
        from: Position;
        to: Position;
    };

    //add missing fullScreen propertoy
    interface EditorConfiguration {
        fullScreen?: boolean;
        lint?: boolean | ((code: string, options: unknown, editor: Editor) => LintError[]);
        filename?: string; // save string into
    }

    function showHint(editor: Editor, callback: () => Hint): void;

    interface Editor {
        //https://stackoverflow.com/a/24574219/13157719
        performLint(): void;
    }
}
