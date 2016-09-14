package testharness

import (
	"context"
	"os"
	"os/exec"
	"testing"

	"github.com/sourcegraph/langserver/client"

	"sourcegraph.com/sourcegraph/sourcegraph/pkg/lsp"
)

var ctx = context.Background()

func initTest(cmd string, tc *TestCase) (*client.LspConn, *exec.Cmd, error) {
	var c *client.LspConn
	var e *exec.Cmd
	var err error

	c, e, err = client.NewStdioClient(ctx, cmd)

	dir, err := os.Getwd()
	if err != nil {
		c.Close()
		e.Process.Kill()
		return nil, nil, err
	}

	err = c.Initialize(ctx, dir+"/test_repos/"+tc.Repo)
	if err != nil {
		c.Close()
		e.Process.Kill()
		return nil, nil, err
	}

	return c, e, nil
}

// RunHoverTests executes a TestCase's hover tests.
func RunHoverTests(cmd string, tc *TestCase, t *testing.T) {
	c, e, err := initTest(cmd, tc)
	if err != nil {
		t.Error(err)
	}

	defer c.Shutdown(ctx)
	defer c.Close()
	defer e.Process.Kill()

	for i, hc := range tc.HoverCases {
		resp, err := c.Hover(ctx, hc.ToRequestParams())
		if err != nil {
			t.Errorf("Error returned for hover (case #%d): %v", i, err)
		}
		checkHoverResponse(i, &hc.Resp, resp, t)
	}
}

func checkHoverResponse(i int, expected *lsp.Hover, got *lsp.Hover, t *testing.T) {
	if expected.Range != got.Range {
		t.Errorf("Range (case #%d): expected %v got %v", i, expected.Range, got.Range)
	}
	if len(expected.Contents) != len(got.Contents) {
		t.Errorf("len(Contents) (case #%d): expected %d got %d", i, len(expected.Contents), len(got.Contents))
	}
	for j, c := range got.Contents {
		e := expected.Contents[j]
		if e != c {
			t.Errorf("Content[%d] (case #%d): expected %v got %v", j, i, e, c)
		}
	}
}

// RunDefinitionTests executes a TestCase's definition tests.
func RunDefinitionTests(cmd string, tc *TestCase, t *testing.T) {
	c, e, err := initTest(cmd, tc)
	if err != nil {
		t.Error(err)
	}

	defer c.Shutdown(ctx)
	defer c.Close()
	defer e.Process.Kill()

	for i, dc := range tc.DefinitionCases {
		resp, err := c.Definition(ctx, dc.ToRequestParams())
		if err != nil {
			t.Errorf("Error returned for definition (case #%d): %v", i, err)
		}
		checkLocationResponse(i, &dc.Resp, resp, t)
	}
}

// RunReferencesTests executes a TestCase's references tests.
func RunReferencesTests(cmd string, tc *TestCase, t *testing.T) {
	c, e, err := initTest(cmd, tc)
	if err != nil {
		t.Error(err)
	}

	defer c.Shutdown(ctx)
	defer c.Close()
	defer e.Process.Kill()

	for i, rc := range tc.ReferencesCases {
		resp, err := c.References(ctx, rc.ToRequestParams())
		if err != nil {
			t.Errorf("Error returned for definition (case #%d): %v", i, err)
		}
		checkLocationResponse(i, &rc.Resp, resp, t)
	}
}

func checkLocationResponse(i int, expected *[]lsp.Location, got *[]lsp.Location, t *testing.T) {
	if len(*expected) != len(*got) {
		t.Errorf("len(Location) (case #%d): expected %d got %d", i, len(*expected), len(*got))
	}
	for j, l := range *got {
		e := (*expected)[j]
		if l != e {
			t.Errorf("Location[%d] (case #%d): expected %v got %v", j, i, e, l)
		}
	}
}
