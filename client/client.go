package client

import (
	"context"
	"fmt"
	"io"
	"net"
	"os/exec"

	"github.com/sourcegraph/go-langserver/pkg/lsp"
	"github.com/sourcegraph/jsonrpc2"
)

// LspConn wraps a jsonrpc2.Conn for communiting with an
// LSP-based language server over stdio or tcp sockets.
type LspConn struct {
	*jsonrpc2.Conn
}

// Initialize makes an `initialize` LSP request.
func (c *LspConn) Initialize(ctx context.Context, rootPath string) error {
	return c.Call(ctx, "initialize", &lsp.InitializeParams{RootPath: rootPath}, nil)
}

// Definition makes an `textDocument/definition` LSP request.
func (c *LspConn) Definition(ctx context.Context, p *lsp.TextDocumentPositionParams) (*[]lsp.Location, error) {
	var locResp []lsp.Location
	err := c.Call(ctx, "textDocument/definition", p, &locResp)
	if err != nil {
		return nil, err
	}
	return &locResp, nil
}

// Hover makes an `textDocument/hover` LSP request.
func (c *LspConn) Hover(ctx context.Context, p *lsp.TextDocumentPositionParams) (*lsp.Hover, error) {
	var hoverResp lsp.Hover
	err := c.Call(ctx, "textDocument/hover", p, &hoverResp)
	if err != nil {
		return nil, err
	}
	return &hoverResp, nil
}

// References makes an `textDocument/references` LSP request.
func (c *LspConn) References(ctx context.Context, p *lsp.TextDocumentPositionParams) (*[]lsp.Location, error) {
	rp := lsp.ReferenceParams{
		TextDocumentPositionParams: *p,
		Context: lsp.ReferenceContext{
			IncludeDeclaration: true,
		},
	}
	var refsResp []lsp.Location
	err := c.Call(ctx, "textDocument/references", rp, &refsResp)
	if err != nil {
		return nil, err
	}
	return &refsResp, nil
}

func (c *LspConn) Symbol(ctx context.Context, p *lsp.WorkspaceSymbolParams) (*[]lsp.SymbolInformation, error) {
	var symResp []lsp.SymbolInformation
	err := c.Call(ctx, "workspace/symbol", p, &symResp)
	if err != nil {
		return nil, err
	}
	return &symResp, nil
}

// Shutdown makes an `shutdown` LSP request.
func (c *LspConn) Shutdown(ctx context.Context) error {
	return c.Call(ctx, "shutdown", nil, nil)
}

// NewTCPClient returns a new LspConn connected to a tcp socket at address.
func NewTCPClient(ctx context.Context, addr string) (*LspConn, error) {
	if addr == "" {
		return nil, fmt.Errorf("provide a command and addr to create a lang server tcp client")
	}

	conn, err := net.Dial("tcp", addr)
	if err != nil {
		return nil, err
	}
	c := LspConn{}
	c.Conn = jsonrpc2.NewConn(ctx, conn, nil)
	return &c, nil
}

type stdrwc struct {
	Stdin  io.WriteCloser
	Stdout io.ReadCloser
}

func (v stdrwc) Read(p []byte) (int, error) {
	return v.Stdout.Read(p)
}

func (v stdrwc) Write(p []byte) (int, error) {
	return v.Stdin.Write(p)
}

func (v stdrwc) Close() error {
	if err := v.Stdin.Close(); err != nil {
		return err
	}
	return v.Stdout.Close()
}

// NewStdioClient returns a new LspConn connected to a process over stdio.
func NewStdioClient(ctx context.Context, cmd string) (*LspConn, *exec.Cmd, error) {
	subProcess := exec.Command(cmd)

	stdin, err := subProcess.StdinPipe()
	if err != nil {
		return nil, nil, err
	}
	stdout, err := subProcess.StdoutPipe()
	if err != nil {
		return nil, nil, err
	}
	if err = subProcess.Start(); err != nil {
		return nil, nil, err
	}

	s := stdrwc{
		Stdin:  stdin,
		Stdout: stdout,
	}
	c := LspConn{}
	c.Conn = jsonrpc2.NewConn(ctx, s, nil)
	return &c, subProcess, nil
}
