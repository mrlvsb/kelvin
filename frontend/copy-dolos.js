// Copies the dolos-web directory from node_modules to web/static,
// so that it can be served by Django.

const fs = require("fs");

fs.cpSync("node_modules/@dodona/dolos-web/dist", "../web/static/dolos", {
    recursive: true
});
