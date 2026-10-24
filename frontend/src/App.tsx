import { useCallback, useEffect, useRef, useState } from "react";
import { Icon } from "./components/Icon";
import { api } from "./services/api";
import type {
  Conversion,
  Dataset,
  Overview,
  Rule,
  Run,
  Version,
} from "./services/api";

type Page = "overview" | "detections" | "testing" | "history";
const labels: Record<Page, string> = {
  overview: "Overview",
  detections: "Detection library",
  testing: "Testing center",
  history: "Execution history",
};
const formatDate = (date: string) =>
  new Date(date).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
const pct = (value: number | null) =>
  value === null ? "—" : `${Math.round(value * 100)}%`;

export default function App() {
  const [page, setPage] = useState<Page>("overview");
  const [rules, setRules] = useState<Rule[]>([]);
  const [overview, setOverview] = useState<Overview | null>(null);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [selected, setSelected] = useState<Rule | null>(null);
  const [yaml, setYaml] = useState("");
  const [conversion, setConversion] = useState<Conversion | null>(null);
  const [versions, setVersions] = useState<Version[]>([]);
  const [search, setSearch] = useState("");
  const [severity, setSeverity] = useState("");
  const [testRule, setTestRule] = useState("");
  const [testDataset, setTestDataset] = useState("");
  const [report, setReport] = useState<Run | null>(null);
  const upload = useRef<HTMLInputElement>(null);
  const fileError = (e: unknown) =>
    setError(e instanceof Error ? e.message : "Unexpected error");

  const refresh = useCallback(async () => {
    const [r, o, d, h] = await Promise.all([
      api<Rule[]>("/rules"),
      api<Overview>("/overview"),
      api<Dataset[]>("/datasets"),
      api<Run[]>("/tests"),
    ]);
    setRules(r);
    setOverview(o);
    setDatasets(d);
    setRuns(h);
  }, []);
  useEffect(() => {
    refresh()
      .catch(fileError)
      .finally(() => setLoading(false));
  }, [refresh]);
  useEffect(() => {
    setConversion(null);
    setNotice("");
  }, [yaml]);
  useEffect(() => {
    if (!editorOpen && !report) return;
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>("[role=dialog]");
    const focusable = () =>
      Array.from(
        dialog?.querySelectorAll<HTMLElement>(
          "button:not(:disabled), a[href], input:not([hidden]), select:not(:disabled), textarea:not(:disabled)",
        ) || [],
      );
    focusable()[0]?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setEditorOpen(false);
        setReport(null);
      }
      if (e.key === "Tab") {
        const items = focusable(),
          first = items[0],
          last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", onKey);
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = old;
      previous?.focus();
    };
  }, [editorOpen, report]);

  async function action(task: () => Promise<void>) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await task();
    } catch (e) {
      fileError(e);
    } finally {
      setBusy(false);
    }
  }
  async function openRule(rule: Rule) {
    await action(async () => {
      const [r, v] = await Promise.all([
        api<Rule>(`/rules/${rule.id}`),
        api<Version[]>(`/rules/${rule.id}/versions`),
      ]);
      setSelected(r);
      setYaml(r.yaml_content || "");
      setVersions(v);
      setEditorOpen(true);
    });
  }
  function newRule() {
    setSelected(null);
    setYaml("");
    setVersions([]);
    setConversion(null);
    setEditorOpen(true);
    setError("");
    setNotice("");
  }
  async function loadExample() {
    await action(async () => {
      const example = await api<{ yaml_content: string }>("/example-rule");
      setYaml(example.yaml_content);
    });
  }
  async function save() {
    await action(async () => {
      const saved = await api<Rule>(
        selected ? `/rules/${selected.id}` : "/rules",
        selected ? "PUT" : "POST",
        {
          yaml_content: yaml,
          ...(selected ? { expected_version: selected.version } : {}),
        },
      );
      setSelected(saved);
      setVersions(await api<Version[]>(`/rules/${saved.id}/versions`));
      await refresh();
      setNotice(`Validated and saved as version ${saved.version}.`);
    });
  }
  const compatible = datasets.filter((d) => d.rule_id === testRule);
  const visibleRules = rules.filter(
    (r) =>
      `${r.title} ${r.techniques.join(" ")}`
        .toLowerCase()
        .includes(search.toLowerCase()) &&
      (!severity || r.level === severity),
  );
  const activeRule = rules.find((r) => r.id === testRule);
  async function execute() {
    await action(async () => {
      const result = await api<Run>("/tests/run", "POST", {
        rule_id: testRule,
        dataset_id: testDataset,
      });
      setReport(result);
      await refresh();
    });
  }
  function navigate(next: Page) {
    setPage(next);
    setError("");
    setNotice("");
  }

  const table = (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th>Detection</th>
            <th>Severity</th>
            <th>ATT&CK mapping</th>
            <th>Latest offline test</th>
            <th>Updated</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {visibleRules.map((rule) => (
            <tr key={rule.id}>
              <td>
                <button
                  className="rule-link"
                  onClick={() => void openRule(rule)}
                >
                  <span className="rule-icon">
                    <Icon name="code" />
                  </span>
                  <span>
                    {rule.title}
                    <small>
                      Windows ·{" "}
                      {rule.logsource.category || rule.logsource.service}{" "}
                      <span className="subtle">
                        / v{rule.version}
                        {!rule.enabled && " / disabled"}
                      </span>
                    </small>
                  </span>
                </button>
              </td>
              <td>
                <span className={`badge severity-${rule.level}`}>
                  {rule.level}
                </span>
              </td>
              <td>
                {rule.techniques.length ? (
                  rule.techniques.map((t) => (
                    <span key={t} className="technique">
                      {t}
                    </span>
                  ))
                ) : (
                  <span className="muted">Unmapped</span>
                )}
              </td>
              <td>
                <Status passed={rule.latest_test?.passed} />
              </td>
              <td className="muted nowrap">{formatDate(rule.updated_at)}</td>
              <td>
                <button
                  className="icon-btn"
                  aria-label={`Open ${rule.title}`}
                  onClick={() => void openRule(rule)}
                >
                  <Icon name="arrow" />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {!visibleRules.length && (
        <div className="empty">
          <div className="empty-symbol">
            <Icon name="shield" size={28} />
          </div>
          <h3>
            {rules.length
              ? "No matching detections"
              : "Build your first detection"}
          </h3>
          <p>
            {rules.length
              ? "Try another title, technique, or severity."
              : "Import a Sigma rule, inspect the query, and put it to the test."}
          </p>
          {!rules.length && (
            <button className="btn secondary" onClick={newRule}>
              <Icon name="plus" />
              Import your first rule
            </button>
          )}
        </div>
      )}
    </div>
  );

  return (
    <div className="shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            navigate("overview");
          }}
        >
          <span className="brand-mark">
            <Icon name="bolt" size={25} />
          </span>
          <span>
            Detection<span className="brand-light">Forge</span>
            <small>DETECTION ENGINEERING</small>
          </span>
        </a>
        <div className="workspace">
          <span className="workspace-icon">DF</span>
          <div>
            Local workspace<small>Phase 1 · Development</small>
          </div>
          <span className="dot" />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          {(Object.keys(labels) as Page[]).map((key, i) => (
            <button
              key={key}
              onClick={() => navigate(key)}
              className={page === key ? "active" : ""}
            >
              <Icon name={["grid", "shield", "flask", "clock"][i]} />
              {labels[key]}
              {key === "detections" && (
                <span className="nav-count">
                  {overview?.total_rules ?? "—"}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="phase-card">
            <span className="eyebrow">
              <span className="dot" /> OFFLINE WORKSPACE
            </span>
            <p>Evidence starts with a test.</p>
            <small>
              Fixture results are separate from live Splunk verification.
            </small>
          </div>
          <div className="local-user">
            <span className="avatar">DE</span>
            <div>
              Detection engineer<small>Local session</small>
            </div>
            <span className="version">v0.1</span>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <span className="muted">Workspace</span>
            <span className="slash">/</span>
            {labels[page]}
          </div>
          <div className="topbar-right">
            <span className="env-badge">
              <span className="dot" />
              LOCAL DEVELOPMENT
            </span>
            <span className="avatar small">DE</span>
          </div>
        </header>
        <div className="content">
          {error && (
            <div className="alert error" role="alert">
              <Icon name="close" />
              <span>{error}</span>
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                ×
              </button>
            </div>
          )}
          {notice && !editorOpen && (
            <div className="alert success" role="status">
              {notice}
            </div>
          )}
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                DETECTIONFORGE /{" "}
                {page === "overview"
                  ? "COMMAND CENTER"
                  : labels[page].toUpperCase()}
              </span>
              <h1>
                {page === "overview"
                  ? "Build detections. Prove they work."
                  : labels[page]}
              </h1>
              <p>
                {page === "overview"
                  ? "Your detection engineering workflow, from Sigma rule to test evidence."
                  : page === "detections"
                    ? "Versioned rules. Validated syntax. A clear path to testable detections."
                    : page === "testing"
                      ? "Evaluate your rules against known event fixtures and inspect every match."
                      : "A reproducible record of every offline fixture test."}
              </p>
            </div>
            <button
              disabled={busy || loading}
              className="btn primary"
              onClick={newRule}
            >
              <Icon name="plus" />
              Import detection
            </button>
          </div>
          {loading ? (
            <div className="panel empty">
              <div className="spinner" />
              <p>Connecting to your workspace…</p>
            </div>
          ) : (
            <>
              {page === "overview" && (
                <>
                  <div className="stats-grid">
                    <Stat
                      icon="shield"
                      label="Total detections"
                      value={overview?.total_rules}
                      foot={`${overview?.valid_rules ?? 0} validated · ${overview?.invalid_rules ?? 0} invalid stored`}
                    />
                    <Stat
                      icon="flask"
                      label="Tested detections"
                      value={overview?.tested_detections}
                      foot={`${overview?.untested_detections ?? 0} current versions untested`}
                    />
                    <Stat
                      icon="check"
                      label="Passing tests"
                      value={overview?.passing_tests}
                      foot="Offline fixture executions"
                      green
                    />
                    <Stat
                      icon="bolt"
                      label="Fixture pass rate"
                      value={overview ? pct(overview.test_pass_rate) : "—"}
                      foot={`${overview?.failing_tests ?? 0} failing executions`}
                      green
                    />
                  </div>
                  <div className="context-strip">
                    <span className="context-icon">
                      <Icon name="flask" />
                    </span>
                    <div>
                      <strong>Prove the rule before the rollout.</strong>
                      <span>
                        This workspace runs deterministic offline tests. Live
                        Splunk verification arrives in Phase 2.
                      </span>
                    </div>
                    <span className="badge neutral">PHASE 1</span>
                  </div>
                  <section className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>
                          Detection library{" "}
                          <span className="count">{rules.length}</span>
                        </h2>
                        <p>Every imported rule starts with validation.</p>
                      </div>
                      <button
                        className="text-btn"
                        onClick={() => navigate("detections")}
                      >
                        View library <Icon name="arrow" size={16} />
                      </button>
                    </div>
                    {table}
                  </section>
                  <div className="lower-grid">
                    <section className="panel">
                      <div className="panel-heading">
                        <div>
                          <h2>Recent executions</h2>
                          <p>Actual results, tied to a rule version.</p>
                        </div>
                        <Icon name="clock" />
                      </div>
                      <RunList
                        runs={overview?.recent_runs.slice(0, 4) || []}
                        rules={rules}
                        onSelect={setReport}
                      />
                    </section>
                    <section className="panel workflow">
                      <span className="eyebrow">THE ENGINEERING LOOP</span>
                      <h2>From idea to evidence.</h2>
                      <p>One workflow. A result you can inspect.</p>
                      {[
                        [
                          "01",
                          "Write & validate",
                          "Import a standard Sigma YAML rule.",
                        ],
                        [
                          "02",
                          "Inspect the query",
                          "Convert with the pySigma Splunk backend.",
                        ],
                        [
                          "03",
                          "Test & investigate",
                          "Compare expected and actual fixture matches.",
                        ],
                      ].map(([n, title, desc]) => (
                        <div className="workflow-step" key={n}>
                          <span>{n}</span>
                          <div>
                            <strong>{title}</strong>
                            <small>{desc}</small>
                          </div>
                        </div>
                      ))}
                    </section>
                  </div>
                </>
              )}
              {page === "detections" && (
                <section className="panel">
                  <div className="panel-heading">
                    <h2>
                      All detections{" "}
                      <span className="count">{rules.length}</span>
                    </h2>
                    <div className="filters">
                      <label className="search">
                        <Icon name="search" />
                        <input
                          aria-label="Search detections"
                          placeholder="Search title or technique…"
                          value={search}
                          onChange={(e) => setSearch(e.target.value)}
                        />
                      </label>
                      <select
                        aria-label="Filter severity"
                        value={severity}
                        onChange={(e) => setSeverity(e.target.value)}
                      >
                        <option value="">All severities</option>
                        {[
                          "informational",
                          "low",
                          "medium",
                          "high",
                          "critical",
                        ].map((s) => (
                          <option key={s}>{s}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  {table}
                </section>
              )}
              {page === "testing" && (
                <div className="testing-grid">
                  <section className="panel test-form">
                    <div className="panel-heading">
                      <div>
                        <h2>Run an offline test</h2>
                        <p>Select a saved rule and a compatible fixture.</p>
                      </div>
                      <Icon name="flask" />
                    </div>
                    <div className="form-body">
                      <label>
                        Detection rule
                        <select
                          value={testRule}
                          onChange={(e) => {
                            setTestRule(e.target.value);
                            setTestDataset("");
                          }}
                        >
                          <option value="">Choose a detection…</option>
                          {rules.map((r) => (
                            <option value={r.id} key={r.id}>
                              {r.title} · v{r.version}
                              {!r.enabled ? " (disabled)" : ""}
                            </option>
                          ))}
                        </select>
                      </label>
                      <label>
                        Event dataset
                        <select
                          value={testDataset}
                          onChange={(e) => setTestDataset(e.target.value)}
                          disabled={!testRule}
                        >
                          <option value="">Choose a compatible dataset…</option>
                          {compatible.map((d) => (
                            <option value={d.id} key={d.id}>
                              {d.id} · {d.category}
                            </option>
                          ))}
                        </select>
                      </label>
                      {testDataset && (
                        <div className="fixture-info">
                          <Icon name="code" />
                          <span>
                            {
                              compatible.find((d) => d.id === testDataset)
                                ?.event_count
                            }{" "}
                            synthetic events{" "}
                            <span className="subtle">
                              /{" "}
                              {
                                compatible.find((d) => d.id === testDataset)
                                  ?.technique
                              }
                            </span>
                          </span>
                        </div>
                      )}
                      {testRule && !compatible.length && (
                        <p className="muted">
                          No bundled dataset matches this rule ID. Custom
                          datasets can be supplied through the API.
                        </p>
                      )}
                      <button
                        disabled={
                          !testRule ||
                          !testDataset ||
                          !activeRule?.enabled ||
                          busy
                        }
                        className="btn primary full"
                        onClick={() => void execute()}
                      >
                        <Icon name="bolt" />
                        {busy ? "Evaluating…" : "Execute offline test"}
                      </button>
                      <p className="fine-print">
                        Tests use the saved rule version. No Splunk connection
                        or event ingestion is performed.
                      </p>
                    </div>
                  </section>
                  <section className="panel test-notes">
                    <span className="eyebrow">KNOW WHAT YOU’RE MEASURING</span>
                    <h2>
                      A pass is evidence.
                      <br />
                      It is not full coverage.
                    </h2>
                    <p>
                      Offline tests compare exact event IDs against the
                      expectations in a synthetic dataset.
                    </p>
                    <div className="note-row">
                      <Icon name="check" />
                      <span>Inspect expected and actual matches</span>
                    </div>
                    <div className="note-row">
                      <Icon name="check" />
                      <span>Track false positives and false negatives</span>
                    </div>
                    <div className="note-row">
                      <Icon name="check" />
                      <span>Download a self-contained JSON report</span>
                    </div>
                    <div className="boundary">
                      Splunk field extraction, ingestion, and live search
                      behavior require Phase 2 verification.
                    </div>
                  </section>
                </div>
              )}
              {(page === "testing" || page === "history") && (
                <section className="panel history-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>
                        Execution history{" "}
                        <span className="count">{runs.length}</span>
                      </h2>
                      <p>
                        Latest 100 runs · immutable rule and dataset snapshots
                      </p>
                    </div>
                    <span className="badge neutral">OFFLINE</span>
                  </div>
                  <RunList runs={runs} rules={rules} onSelect={setReport} />
                </section>
              )}
            </>
          )}
          <footer>
            <span>
              <span className="dot" /> DetectionForge{" "}
              <span className="subtle">/</span> Detection as code
            </span>
            <span>Local workspace · Offline fixture metrics</span>
          </footer>
        </div>
      </main>
      {editorOpen && (
        <div className="modal-backdrop">
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="editor-title"
            className="modal editor-modal"
          >
            <div className="modal-header">
              <div>
                <span className="eyebrow">DETECTION WORKBENCH</span>
                <h2 id="editor-title">
                  {selected ? selected.title : "Import a Sigma detection"}
                </h2>
              </div>
              <button
                className="icon-btn"
                aria-label="Close editor"
                onClick={() => setEditorOpen(false)}
              >
                <Icon name="close" />
              </button>
            </div>
            <div className="modal-body">
              {error && (
                <div className="alert error" role="alert">
                  {error}
                </div>
              )}
              {notice && (
                <div className="alert success" role="status">
                  {notice}
                </div>
              )}
              <div className="editor-toolbar">
                <span className="badge neutral">
                  {selected ? `SAVED VERSION ${selected.version}` : "NEW RULE"}
                </span>
                <div>
                  <input
                    ref={upload}
                    hidden
                    type="file"
                    accept=".yml,.yaml"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) {
                        if (f.size > 65536) setError("Rule exceeds 64 KiB");
                        else void f.text().then(setYaml).catch(fileError);
                      }
                      e.target.value = "";
                    }}
                  />
                  <button
                    disabled={busy}
                    className="text-btn"
                    onClick={() => upload.current?.click()}
                  >
                    Choose YAML file
                  </button>
                  <button
                    className="text-btn"
                    onClick={() => void loadExample()}
                    disabled={busy}
                  >
                    Load PowerShell example
                  </button>
                </div>
              </div>
              <div className="editor-grid">
                <div>
                  <label className="code-label" htmlFor="sigma-editor">
                    <Icon name="code" /> SIGMA YAML <span>64 KiB maximum</span>
                  </label>
                  <textarea
                    disabled={busy}
                    id="sigma-editor"
                    className="yaml-editor"
                    value={yaml}
                    onChange={(e) => setYaml(e.target.value)}
                    spellCheck={false}
                    placeholder={
                      "title: My detection\nid: <UUID>\nlogsource:\n  product: windows\n  category: process_creation\n…"
                    }
                    aria-label="Sigma YAML editor"
                  />
                </div>
                <div className="conversion-pane">
                  <div className="code-label">
                    <Icon name="bolt" /> SPLUNK SPL <span>Preview only</span>
                  </div>
                  {conversion ? (
                    <>
                      <pre className="query">
                        {conversion.queries.join("\n\n")}
                      </pre>
                      <p className="fine-print">{conversion.warning}</p>
                    </>
                  ) : (
                    <div className="conversion-empty">
                      <Icon name="code" size={28} />
                      <h3>Inspect the generated query</h3>
                      <p>
                        Convert the current editor content with the Sysmon
                        raw-event profile.
                      </p>
                    </div>
                  )}
                  <div className="editor-info">
                    <span className="eyebrow">
                      SUPPORTED CONVERSION PROFILE
                    </span>
                    <p>Windows · Sysmon process creation</p>
                    <small>
                      Canonical EventID maps to EventCode. Deployment mappings
                      are configured on the backend.
                    </small>
                  </div>
                </div>
              </div>
              {selected && (
                <div className="saved-meta">
                  <div>
                    <span className="eyebrow">ATT&CK TAGS</span>
                    <p>
                      {selected.techniques.join(", ") || "No technique tags"}{" "}
                      <span className="subtle">
                        · catalog validation deferred
                      </span>
                    </p>
                  </div>
                  <div>
                    <span className="eyebrow">IMMUTABLE VERSIONS</span>
                    <div className="version-buttons">
                      {versions.map((v) => (
                        <button
                          key={v.version}
                          className="badge neutral"
                          onClick={() => {
                            setYaml(v.yaml_content);
                            setNotice(
                              `Loaded v${v.version} into the editor. Save to create a new version.`,
                            );
                          }}
                        >
                          v{v.version}
                        </button>
                      ))}
                    </div>
                  </div>
                  <button
                    disabled={busy}
                    className="btn secondary"
                    onClick={() =>
                      void action(async () => {
                        const result = await api<Rule>(
                          `/rules/${selected.id}/enabled`,
                          "PATCH",
                          {
                            enabled: !selected.enabled,
                            expected_version: selected.version,
                          },
                        );
                        setSelected({
                          ...result,
                          yaml_content: selected.yaml_content,
                        });
                        setVersions(
                          await api<Version[]>(
                            `/rules/${selected.id}/versions`,
                          ),
                        );
                        await refresh();
                        setNotice(
                          result.enabled ? "Rule enabled." : "Rule disabled.",
                        );
                      })
                    }
                  >
                    {selected.enabled ? "Disable rule" : "Enable rule"}
                  </button>
                </div>
              )}
            </div>
            <div className="modal-footer">
              <span className="fine-print">
                {selected
                  ? "Saving creates a new immutable version."
                  : "Imports are validated before storage."}
              </span>
              <div>
                <button
                  disabled={busy || !yaml}
                  className="btn secondary"
                  onClick={() =>
                    void action(async () => {
                      await api("/rules/validate", "POST", {
                        yaml_content: yaml,
                      });
                      setNotice(
                        "Valid Sigma rule. ATT&CK tags have not been checked against the catalog.",
                      );
                    })
                  }
                >
                  Validate
                </button>
                <button
                  disabled={busy || !yaml}
                  className="btn secondary"
                  onClick={() =>
                    void action(async () =>
                      setConversion(
                        await api<Conversion>("/rules/convert", "POST", {
                          yaml_content: yaml,
                        }),
                      ),
                    )
                  }
                >
                  Generate SPL
                </button>
                <button
                  disabled={busy || !yaml}
                  className="btn primary"
                  onClick={() => void save()}
                >
                  <Icon name="check" />
                  {busy
                    ? "Working…"
                    : selected
                      ? "Save version"
                      : "Import rule"}
                </button>
              </div>
            </div>
          </section>
        </div>
      )}
      {report && (
        <div className="modal-backdrop">
          <section
            className="modal report-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="report-title"
          >
            <div className="modal-header">
              <div>
                <span className="eyebrow">OFFLINE EXECUTION REPORT</span>
                <h2 id="report-title">{report.dataset_id}</h2>
              </div>
              <button
                className="icon-btn"
                aria-label="Close report"
                onClick={() => setReport(null)}
              >
                <Icon name="close" />
              </button>
            </div>
            <div className="modal-body">
              <div className="report-banner">
                <Status passed={report.passed} />
                <span>
                  Rule v{report.rule_version} · {report.duration_ms} ms ·{" "}
                  {formatDate(report.created_at)}
                </span>
              </div>
              <p className="fine-print">{report.scope}</p>
              <div className="report-metrics">
                {[
                  ["True positives", report.metrics.true_positives],
                  ["False positives", report.metrics.false_positives],
                  ["True negatives", report.metrics.true_negatives],
                  ["False negatives", report.metrics.false_negatives],
                  ["Precision", pct(report.metrics.precision)],
                  ["Recall", pct(report.metrics.recall)],
                ].map(([l, v]) => (
                  <div key={l}>
                    <small>{l}</small>
                    <strong>{v}</strong>
                  </div>
                ))}
              </div>
              <div className="comparison">
                <div>
                  <h3>Expected event IDs</h3>
                  <pre>{report.expected_event_ids.join("\n") || "(none)"}</pre>
                </div>
                <div>
                  <h3>Actual event IDs</h3>
                  <pre>{report.actual_event_ids.join("\n") || "(none)"}</pre>
                </div>
              </div>
              {!report.passed && (
                <div className="alert error">
                  Missing: {report.missing_event_ids.join(", ") || "none"}
                  <br />
                  Unexpected: {report.unexpected_event_ids.join(", ") || "none"}
                </div>
              )}
              <h3>Matched events</h3>
              {report.matched_events.length ? (
                report.matched_events.map((e) => (
                  <details key={e.id}>
                    <summary>
                      {e.id} <span className="muted">{e.timestamp}</span>
                    </summary>
                    <pre>{JSON.stringify(e.fields, null, 2)}</pre>
                  </details>
                ))
              ) : (
                <p className="muted">No events matched this fixture.</p>
              )}
              <p className="fine-print">
                Run ID: {report.id}. Precision and recall are undefined (—) when
                their denominator is zero.
              </p>
            </div>
            <div className="modal-footer">
              <span className="fine-print">
                Synthetic fixture metrics · not production performance
              </span>
              <a
                className="btn primary"
                href={`/api/tests/${report.id}/report`}
                download
              >
                <Icon name="download" />
                Download JSON report
              </a>
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function Status({ passed }: { passed?: boolean }) {
  return passed === undefined ? (
    <span className="status untested">
      <span />
      Untested
    </span>
  ) : (
    <span className={`status ${passed ? "pass" : "fail"}`}>
      <Icon name={passed ? "check" : "close"} size={13} />
      {passed ? "PASS" : "FAIL"}
    </span>
  );
}
function Stat({
  icon,
  label,
  value,
  foot,
  green,
}: {
  icon: string;
  label: string;
  value?: number | string;
  foot: string;
  green?: boolean;
}) {
  return (
    <div className="stat">
      <div className="stat-label">
        {label}
        <Icon name={icon} />
      </div>
      <strong className={green ? "green" : ""}>{value ?? "—"}</strong>
      <small>{foot}</small>
    </div>
  );
}
function RunList({
  runs,
  rules,
  onSelect,
}: {
  runs: Run[];
  rules: Rule[];
  onSelect: (run: Run) => void;
}) {
  return runs.length ? (
    <div className="run-list">
      {runs.map((run) => (
        <button className="run-row" key={run.id} onClick={() => onSelect(run)}>
          <span className={`run-symbol ${run.passed ? "green" : "red"}`}>
            <Icon name={run.passed ? "check" : "close"} />
          </span>
          <span className="run-name">
            <strong>
              {rules.find((r) => r.id === run.rule_id)?.title || run.rule_id}
            </strong>
            <small>
              {run.dataset_id} · v{run.rule_version} · offline
            </small>
          </span>
          <span className="run-time">
            {formatDate(run.created_at)}
            <small>{run.duration_ms} ms</small>
          </span>
          <Icon name="arrow" size={16} />
        </button>
      ))}
    </div>
  ) : (
    <div className="empty compact">
      <Icon name="clock" size={25} />
      <h3>No test executions yet</h3>
      <p>Run your first fixture test in the Testing center.</p>
    </div>
  );
}
