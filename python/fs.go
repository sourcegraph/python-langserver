package python

import (
	"path/filepath"
	"strings"
)

func (h *Handler) filePath(uri string) string {
	uri = strings.TrimPrefix(uri, "file://")
	if filepath.IsAbs(uri) {
		return uri
	}

	return h.init.RootPath + uri
}
