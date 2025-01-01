import 'codemirror';

declare module 'codemirror' {
    //add missing fullScreen propertoy
    interface EditorConfiguration {
        fullScreen?: boolean;
        lint?: boolean;
        filename?: string; // save string into
    }
}
