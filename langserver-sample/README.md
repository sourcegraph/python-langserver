# Sample Language Server

1. Build and install `langserver-sample` into your `$PATH`: (from this directory) `go install .`.
1. Follow the [instructions to install and run the vscode-client extension](../vscode-client/README.md).
1. In VSCode with the vscode-client extension installed, create a new text file and type some text.
Move your mouse cursor over the text, and you should see "Hello over LSP!" in a tooltip. Right click on
any text and click "Go to Definition", and you'll be taken to the beginning of the file. Right click on any
text and click "Find All References", and if your text is longer than 6 characters, you'll be shown two
references in the first line of your file.

To view `langserver-sample`'s stderr in vscode, select View → Output.
