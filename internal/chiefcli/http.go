package chiefcli

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
)

func getJSON(cfg Config, path string, out any) error {
	return doJSON(http.MethodGet, cfg.LedgerURL, cfg.LedgerFallback, path, nil, out)
}

func postJSON(cfg Config, path string, body any, out any) error {
	payload, err := json.Marshal(body)
	if err != nil {
		return err
	}
	return doJSON(http.MethodPost, cfg.LedgerURL, cfg.LedgerFallback, path, payload, out)
}

func doJSON(method string, primary string, fallback string, path string, body []byte, out any) error {
	err := doJSONOnce(method, primary, path, body, out)
	if err == nil || fallback == "" {
		return err
	}
	return doJSONOnce(method, fallback, path, body, out)
}

func doJSONOnce(method string, base string, path string, body []byte, out any) error {
	url := strings.TrimRight(base, "/") + path
	var reader io.Reader
	if body != nil {
		reader = bytes.NewReader(body)
	}
	req, err := http.NewRequest(method, url, reader)
	if err != nil {
		return err
	}
	req.Header.Set("Accept", "application/json, text/event-stream")
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("ledger request failed: HTTP %d %s", resp.StatusCode, strings.TrimSpace(string(data)))
	}
	if out == nil {
		return nil
	}
	if len(data) == 0 {
		return nil
	}
	if err := json.Unmarshal(data, out); err != nil {
		return fmt.Errorf("ledger response was not valid JSON: %s", err.Error())
	}
	return nil
}
