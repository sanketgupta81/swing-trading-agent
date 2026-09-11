import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { api, type PlaybookTreeEntry } from '@/lib/api';

// ─── Shared ───────────────────────────────────────────────────────────────

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-xs font-medium text-foreground">{label}</label>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function TabButton({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
        active
          ? 'bg-primary text-primary-foreground font-medium'
          : 'text-muted-foreground hover:text-foreground hover:bg-secondary'
      }`}
    >
      {label}
    </button>
  );
}

// ─── General Tab ──────────────────────────────────────────────────────────

interface ModelSettings {
  llm_provider: 'fastrouter' | 'bedrock' | 'openai' | 'anthropic';
  fastrouter_model_id: string;
  fastrouter_base_url: string;
  broker_type: 'fyers' | 'alpaca';
  market_country: 'IN' | 'US';
  indian_universe: 'nifty50' | 'nifty100' | 'nifty500';
  model_id: string;
  extended_thinking_enabled: boolean;
  extended_thinking_budget: number;
  extended_thinking_effort: string;
}

const DEFAULT_MODEL: ModelSettings = {
  llm_provider: 'fastrouter',
  fastrouter_model_id: 'anthropic/claude-3.5-sonnet',
  fastrouter_base_url: 'https://api.fastrouter.ai/api/v1',
  broker_type: 'fyers',
  market_country: 'IN',
  indian_universe: 'nifty50',
  model_id: 'us.anthropic.claude-haiku-4-5-20251001-v1:0',
  extended_thinking_enabled: false,
  extended_thinking_budget: 2048,
  extended_thinking_effort: 'medium',
};

function GeneralTab() {
  const [model, setModel] = useState<ModelSettings>(DEFAULT_MODEL);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/settings/model')
      .then((r) => (r.ok ? r.json() : DEFAULT_MODEL))
      .then(setModel)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function saveModel() {
    setSaved(false);
    await fetch('/api/settings/model', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(model),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function updateModel<K extends keyof ModelSettings>(field: K, value: ModelSettings[K]) {
    setModel((prev) => ({ ...prev, [field]: value }));
  }

  const isClaudeModel = (model.model_id || '').toLowerCase().includes('anthropic');
  const isNovaModel = (model.model_id || '').toLowerCase().includes('nova');

  if (loading) return <p className="text-muted-foreground text-sm">Loading...</p>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            Trading Venue & Market
            <Badge variant="secondary" className="text-[10px]">
              {model.broker_type === 'fyers' ? 'India (NSE/BSE)' : 'United States'}
            </Badge>
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Configure target broker and market universe.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Broker">
            <select
              className="input-field text-xs"
              value={model.broker_type}
              onChange={(e) => {
                const b = e.target.value as 'fyers' | 'alpaca';
                updateModel('broker_type', b);
                updateModel('market_country', b === 'fyers' ? 'IN' : 'US');
              }}
            >
              <option value="fyers">Fyers (India — NSE/BSE Equity CNC)</option>
              <option value="alpaca">Alpaca Markets (US — Paper / Live)</option>
            </select>
          </Field>

          {model.broker_type === 'fyers' && (
            <Field label="Indian Market Universe">
              <select
                className="input-field text-xs"
                value={model.indian_universe}
                onChange={(e) => updateModel('indian_universe', e.target.value as any)}
              >
                <option value="nifty50">Nifty 50 (Recommended — High Liquidity Blue Chips)</option>
                <option value="nifty100">Nifty 100 (Large & Mid Cap)</option>
                <option value="nifty500">Nifty 500 (Broad Market)</option>
              </select>
            </Field>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            LLM Provider & Reasoning Engine
            <Badge variant="secondary" className="text-[10px]">
              {model.llm_provider === 'fastrouter' ? 'FastRouter.ai' : 'AWS Bedrock'}
            </Badge>
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Foundation model that powers the Research Agent and Portfolio Manager Agent.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <Field label="Provider">
            <select
              className="input-field text-xs"
              value={model.llm_provider}
              onChange={(e) => updateModel('llm_provider', e.target.value as any)}
            >
              <option value="fastrouter">FastRouter.ai (OpenAI-compatible unified gateway)</option>
              <option value="bedrock">AWS Bedrock (Amazon IAM / Claude & Nova)</option>
            </select>
          </Field>

          {model.llm_provider === 'fastrouter' ? (
            <>
              <Field label="FastRouter Model ID">
                <input
                  className="input-field font-mono text-xs"
                  placeholder="anthropic/claude-3.5-sonnet"
                  value={model.fastrouter_model_id}
                  onChange={(e) => updateModel('fastrouter_model_id', e.target.value)}
                />
                <div className="flex flex-wrap gap-1.5 mt-1.5">
                  {['anthropic/claude-3.5-sonnet', 'openai/gpt-4o', 'deepseek/deepseek-chat', 'fastrouter/auto'].map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => updateModel('fastrouter_model_id', m)}
                      className="px-2 py-0.5 text-[10px] rounded border border-border bg-secondary hover:bg-secondary/80 text-foreground"
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </Field>
            </>
          ) : (
            <>
              <Field label="Bedrock Model ID">
                <input
                  className="input-field font-mono text-xs"
                  placeholder="us.anthropic.claude-..."
                  value={model.model_id}
                  onChange={(e) => updateModel('model_id', e.target.value)}
                />
              </Field>

              <div className="flex items-center gap-3 pt-1">
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    className="sr-only peer"
                    checked={model.extended_thinking_enabled}
                    onChange={(e) => updateModel('extended_thinking_enabled', e.target.checked)}
                  />
                  <div className="w-9 h-5 bg-muted rounded-full peer peer-checked:bg-primary transition-colors after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full" />
                </label>
                <span className="text-xs font-medium">Extended Thinking</span>
                {model.extended_thinking_enabled && (
                  <Badge variant="outline" className="text-[10px]">
                    {isClaudeModel ? `${model.extended_thinking_budget} tokens` : isNovaModel ? model.extended_thinking_effort : 'unknown model'}
                  </Badge>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center gap-3">
        <button
          className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity"
          onClick={saveModel}
        >
          Save Settings
        </button>
        {saved && <span className="text-xs text-gain">Saved</span>}
      </div>
    </div>
  );
}

// ─── API Keys Tab ─────────────────────────────────────────────────────────

interface ApiKeys {
  fastrouter_api_key?: string;
  fyers_client_id?: string;
  fyers_secret_key?: string;
  fyers_access_token?: string;
  fyers_pin?: string;
  fyers_totp_key?: string;
  alpaca_paper_account_name?: string;
  alpaca_paper_api_key?: string;
  alpaca_paper_secret_key?: string;
  alpaca_live_api_key?: string;
  alpaca_live_secret_key?: string;
  polygon_api_key?: string;
}

const EMPTY_KEYS: ApiKeys = {
  fastrouter_api_key: '',
  fyers_client_id: '',
  fyers_secret_key: '',
  fyers_access_token: '',
  fyers_pin: '',
  fyers_totp_key: '',
  alpaca_paper_account_name: '',
  alpaca_paper_api_key: '',
  alpaca_paper_secret_key: '',
  alpaca_live_api_key: '',
  alpaca_live_secret_key: '',
  polygon_api_key: '',
};

function ApiKeysTab() {
  const [keys, setKeys] = useState<ApiKeys>(EMPTY_KEYS);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/settings/keys')
      .then((r) => (r.ok ? r.json() : EMPTY_KEYS))
      .then(setKeys)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function saveKeys() {
    setSaved(false);
    await fetch('/api/settings/keys', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(keys),
    });
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function updateKey(field: keyof ApiKeys, value: string) {
    setKeys((prev) => ({ ...prev, [field]: value }));
  }

  if (loading) return <p className="text-muted-foreground text-sm">Loading...</p>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            FastRouter.ai
            <Badge variant="secondary" className="text-[10px]">fastrouter.ai</Badge>
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            API key for unified LLM access across Claude, GPT-4o, DeepSeek, and more.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Field label="FastRouter API Key">
            <input
              type="password"
              className="input-field font-mono text-xs"
              placeholder="••••••••"
              value={keys.fastrouter_api_key || ''}
              onChange={(e) => updateKey('fastrouter_api_key', e.target.value)}
            />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            Fyers Broker (India)
            <Badge variant="secondary" className="text-[10px]">myapi.fyers.in</Badge>
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Fyers API v3 credentials for NSE/BSE cash delivery trading and account sync.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Field label="Client ID / App ID">
            <input
              className="input-field font-mono text-xs"
              placeholder="e.g. XC12345-100"
              value={keys.fyers_client_id || ''}
              onChange={(e) => updateKey('fyers_client_id', e.target.value)}
            />
          </Field>
          <Field label="Secret Key">
            <input
              type="password"
              className="input-field font-mono text-xs"
              placeholder="••••••••"
              value={keys.fyers_secret_key || ''}
              onChange={(e) => updateKey('fyers_secret_key', e.target.value)}
            />
          </Field>
          <Field label="Daily Access Token">
            <input
              type="password"
              className="input-field font-mono text-xs"
              placeholder="Paste today's Fyers access token"
              value={keys.fyers_access_token || ''}
              onChange={(e) => updateKey('fyers_access_token', e.target.value)}
            />
            <p className="text-[10px] text-muted-foreground mt-1">
              Fyers tokens expire daily per SEBI mandate.
            </p>
          </Field>

          <div className="pt-2 border-t border-border/50">
            <p className="text-xs font-semibold text-foreground mb-2">Optional: Unattended Daily Auto-Login (TOTP)</p>
            <div className="grid grid-cols-2 gap-3">
              <Field label="4-Digit Account PIN">
                <input
                  type="password"
                  className="input-field font-mono text-xs"
                  placeholder="••••"
                  maxLength={4}
                  value={keys.fyers_pin || ''}
                  onChange={(e) => updateKey('fyers_pin', e.target.value)}
                />
              </Field>
              <Field label="TOTP Secret Key">
                <input
                  type="password"
                  className="input-field font-mono text-xs"
                  placeholder="32-character TOTP key"
                  value={keys.fyers_totp_key || ''}
                  onChange={(e) => updateKey('fyers_totp_key', e.target.value)}
                />
              </Field>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            Alpaca — Paper Account
            <Badge variant="secondary" className="text-[10px]">paper-api.alpaca.markets</Badge>
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Paper trading credentials (for US markets).
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Field label="API Key">
            <input
              className="input-field font-mono text-xs"
              placeholder="PK..."
              value={keys.alpaca_paper_api_key || ''}
              onChange={(e) => updateKey('alpaca_paper_api_key', e.target.value)}
            />
          </Field>
          <Field label="Secret Key">
            <input
              type="password"
              className="input-field font-mono text-xs"
              placeholder="••••••••"
              value={keys.alpaca_paper_secret_key || ''}
              onChange={(e) => updateKey('alpaca_paper_secret_key', e.target.value)}
            />
          </Field>
        </CardContent>
      </Card>


      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            Alpaca — Live Account
            <Badge variant="secondary" className="text-[10px]">api.alpaca.markets</Badge>
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Live trading credentials. Only needed if you plan to trade with real money.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Field label="API Key">
            <input
              className="input-field font-mono text-xs"
              placeholder="AK..."
              value={keys.alpaca_live_api_key}
              onChange={(e) => updateKey('alpaca_live_api_key', e.target.value)}
            />
          </Field>
          <Field label="Secret Key">
            <input
              type="password"
              className="input-field font-mono text-xs"
              placeholder="••••••••"
              value={keys.alpaca_live_secret_key}
              onChange={(e) => updateKey('alpaca_live_secret_key', e.target.value)}
            />
          </Field>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            Polygon.io
            <Badge variant="secondary" className="text-[10px]">News Data</Badge>
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Optional. Used for historical news in backtesting. Live trading uses yfinance news (no key needed).
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <Field label="API Key">
            <input
              type="password"
              className="input-field font-mono text-xs"
              placeholder="••••••••"
              value={keys.polygon_api_key}
              onChange={(e) => updateKey('polygon_api_key', e.target.value)}
            />
          </Field>
        </CardContent>
      </Card>

      <div className="flex items-center gap-3">
        <button
          className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:opacity-90 transition-opacity"
          onClick={saveKeys}
        >
          Save API Keys
        </button>
        {saved && <span className="text-xs text-gain">Saved</span>}
      </div>

      <p className="text-xs text-muted-foreground">
        Keys are stored locally on the server. They are never sent to external services except the respective APIs.
      </p>
    </div>
  );
}

// ─── Playbook Tab ─────────────────────────────────────────────────────────

interface TopicItem {
  chapter: string;
  topic: string;
  title: string;
  modified: boolean;
}

interface ChapterGroup {
  chapter: string;
  topics: TopicItem[];
}

function PlaybookTab() {
  const [tree, setTree] = useState<ChapterGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTopic, setActiveTopic] = useState<TopicItem | null>(null);
  const [content, setContent] = useState('');
  const [defaultContent, setDefaultContent] = useState('');
  const [history, setHistory] = useState<{ ts: number }[]>([]);
  const [showDiff, setShowDiff] = useState(false);
  const [isModified, setIsModified] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState('');
  const [expandedChapters, setExpandedChapters] = useState<Set<string>>(new Set());
  const [historyContent, setHistoryContent] = useState<string | null>(null);
  const [historyTs, setHistoryTs] = useState<number | null>(null);
  const [loadingContent, setLoadingContent] = useState(false);

  const loadTree = useCallback(() => {
    api.getPlaybookTree().then((data) => {
      const groups: ChapterGroup[] = [];
      for (const entry of data) {
        if (entry.topics) {
          groups.push({ chapter: entry.chapter, topics: entry.topics });
        } else if (entry.topic === 'overview') {
          groups.unshift({
            chapter: '_root',
            topics: [{ chapter: '_root', topic: 'overview', title: entry.title || 'Overview', modified: entry.modified || false }],
          });
        }
      }
      setTree(groups);
      setExpandedChapters(new Set(groups.map(g => g.chapter)));
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadTree(); }, [loadTree]);

  async function openTopic(item: TopicItem) {
    setActiveTopic(item);
    setDirty(false);
    setSavedMsg('');
    setShowDiff(false);
    setHistoryContent(null);
    setHistoryTs(null);
    setLoadingContent(true);
    try {
      const [topicData, defaultData] = await Promise.all([
        api.getPlaybookTopic(item.chapter, item.topic),
        api.getPlaybookDefault(item.chapter, item.topic),
      ]);
      setContent(topicData.content);
      setDefaultContent(defaultData.content);
      setIsModified(topicData.is_modified);
      setHistory(topicData.history);
    } catch {
      setContent('');
      setDefaultContent('');
    } finally {
      setLoadingContent(false);
    }
  }

  async function save() {
    if (!activeTopic) return;
    setSaving(true);
    try {
      await api.savePlaybookTopic(activeTopic.chapter, activeTopic.topic, content);
      setDirty(false);
      setIsModified(true);
      setSavedMsg('Saved');
      setTimeout(() => setSavedMsg(''), 2000);
      const topicData = await api.getPlaybookTopic(activeTopic.chapter, activeTopic.topic);
      setHistory(topicData.history);
      loadTree();
    } catch {
      setSavedMsg('Error saving');
    } finally {
      setSaving(false);
    }
  }

  async function resetToDefault() {
    if (!activeTopic) return;
    if (!confirm('Reset to default? Your current changes will be saved to history.')) return;
    try {
      await api.resetPlaybookTopic(activeTopic.chapter, activeTopic.topic);
      setContent(defaultContent);
      setIsModified(false);
      setDirty(false);
      setSavedMsg('Reset to default');
      setTimeout(() => setSavedMsg(''), 2000);
      const topicData = await api.getPlaybookTopic(activeTopic.chapter, activeTopic.topic);
      setHistory(topicData.history);
      loadTree();
    } catch {
      setSavedMsg('Error resetting');
    }
  }

  async function loadHistoryVersion(ts: number) {
    if (!activeTopic) return;
    try {
      const data = await api.getPlaybookHistory(activeTopic.chapter, activeTopic.topic, ts);
      setHistoryContent(data.content);
      setHistoryTs(ts);
    } catch { /* ignore */ }
  }

  function restoreVersion() {
    if (historyContent == null) return;
    setContent(historyContent);
    setDirty(true);
    setHistoryContent(null);
    setHistoryTs(null);
  }

  function toggleChapter(chapter: string) {
    setExpandedChapters(prev => {
      const next = new Set(prev);
      if (next.has(chapter)) next.delete(chapter);
      else next.add(chapter);
      return next;
    });
  }

  function formatTs(ts: number) {
    const d = new Date(ts * 1000);
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  }

  const isActive = (t: TopicItem) =>
    activeTopic?.chapter === t.chapter && activeTopic?.topic === t.topic;

  if (loading) return <p className="text-muted-foreground text-sm">Loading playbook...</p>;

  return (
    <div className="flex gap-4" style={{ minHeight: 'calc(100vh - 200px)' }}>
      {/* ── Left: Table of Contents ── */}
      <div className="w-56 flex-shrink-0 space-y-0.5 overflow-y-auto border-r border-border pr-3">
        {tree.map(group => (
          <div key={group.chapter}>
            {group.chapter === '_root' ? (
              group.topics.map(t => (
                <button
                  key={`${t.chapter}/${t.topic}`}
                  onClick={() => openTopic(t)}
                  className={`w-full text-left px-2 py-1.5 rounded-md text-xs transition-colors flex items-center gap-1.5 ${
                    isActive(t)
                      ? 'bg-primary/10 text-primary font-medium'
                      : 'text-foreground hover:bg-secondary/50'
                  }`}
                >
                  {t.title}
                  {t.modified && <span className="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />}
                </button>
              ))
            ) : (
              <>
                <button
                  onClick={() => toggleChapter(group.chapter)}
                  className="w-full text-left px-2 py-1.5 flex items-center gap-1.5 mt-2"
                >
                  <span className="text-[9px] text-muted-foreground">
                    {expandedChapters.has(group.chapter) ? '▼' : '▶'}
                  </span>
                  <span className="text-xs font-semibold capitalize text-muted-foreground">
                    {group.chapter}
                  </span>
                  {group.topics.some(t => t.modified) && (
                    <span className="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />
                  )}
                </button>
                {expandedChapters.has(group.chapter) && (
                  <div className="ml-1">
                    {group.topics.map(t => (
                      <button
                        key={`${t.chapter}/${t.topic}`}
                        onClick={() => openTopic(t)}
                        className={`w-full text-left px-2 py-1.5 rounded-md text-xs transition-colors flex items-center gap-1.5 ${
                          isActive(t)
                            ? 'bg-primary/10 text-primary font-medium'
                            : 'text-foreground hover:bg-secondary/50'
                        }`}
                      >
                        <span className="truncate">{t.title}</span>
                        {t.modified && <span className="w-1.5 h-1.5 rounded-full bg-primary flex-shrink-0" />}
                      </button>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        ))}
      </div>

      {/* ── Right: Content / Editor ── */}
      <div className="flex-1 min-w-0">
        {!activeTopic && (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-muted-foreground">Select a topic from the left to view or edit.</p>
          </div>
        )}

        {activeTopic && loadingContent && (
          <p className="text-sm text-muted-foreground">Loading...</p>
        )}

        {activeTopic && !loadingContent && (
          <div className="space-y-3">
            {/* Header */}
            <div className="flex items-center gap-3">
              <h2 className="text-sm font-semibold">
                {activeTopic.chapter === '_root' ? '' : <span className="text-muted-foreground">{activeTopic.chapter} / </span>}
                {activeTopic.title}
              </h2>
              {isModified && <Badge variant="secondary" className="text-[9px]">Modified</Badge>}
              {dirty && <Badge variant="outline" className="text-[9px] text-yellow-600">Unsaved</Badge>}
            </div>

            {/* History bar */}
            {history.length > 0 && (
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-[10px] text-muted-foreground">History:</span>
                <button
                  onClick={() => { setHistoryContent(null); setHistoryTs(null); }}
                  className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                    historyTs == null
                      ? 'border-primary bg-primary/10 text-foreground'
                      : 'border-border hover:border-ring/40 text-muted-foreground hover:text-foreground'
                  }`}
                >
                  Current
                </button>
                {history.map(h => (
                  <button
                    key={h.ts}
                    onClick={() => loadHistoryVersion(h.ts)}
                    className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                      historyTs === h.ts
                        ? 'border-primary bg-primary/10 text-foreground'
                        : 'border-border hover:border-ring/40 text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {formatTs(h.ts)}
                  </button>
                ))}
              </div>
            )}

            {/* History preview */}
            {historyContent != null && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-muted-foreground">Viewing: {formatTs(historyTs!)}</span>
                  <button
                    onClick={restoreVersion}
                    className="px-2 py-0.5 rounded bg-primary text-primary-foreground text-[10px] hover:opacity-90"
                  >
                    Restore this version
                  </button>
                </div>
                <pre className="text-xs font-mono whitespace-pre-wrap bg-secondary/30 rounded-md p-3 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 340px)' }}>
                  {historyContent}
                </pre>
              </div>
            )}

            {/* Editor */}
            {historyContent == null && (
              <>
                {/* Toolbar */}
                <div className="flex items-center gap-2">
                  {isModified && (
                    <button
                      onClick={() => setShowDiff(!showDiff)}
                      className={`text-[10px] px-2 py-0.5 rounded border transition-colors ${
                        showDiff ? 'border-primary bg-primary/10' : 'border-border hover:border-ring/40'
                      } text-muted-foreground`}
                    >
                      {showDiff ? 'Hide' : 'Show'} Default
                    </button>
                  )}
                  <div className="flex-1" />
                  <button
                    onClick={save}
                    disabled={saving || !dirty}
                    className="px-3 py-1 rounded-md bg-primary text-primary-foreground text-xs font-medium hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    {saving ? 'Saving...' : 'Save'}
                  </button>
                  {isModified && (
                    <button
                      onClick={resetToDefault}
                      className="px-3 py-1 rounded-md border border-border text-xs text-muted-foreground hover:text-foreground hover:border-ring/40 transition-colors"
                    >
                      Reset
                    </button>
                  )}
                  {savedMsg && <span className="text-[10px] text-gain">{savedMsg}</span>}
                </div>

                {showDiff && (
                  <div>
                    <p className="text-[10px] text-muted-foreground uppercase mb-1">Default (original)</p>
                    <pre className="text-xs font-mono whitespace-pre-wrap bg-secondary/30 rounded-md p-3 max-h-[200px] overflow-y-auto">
                      {defaultContent}
                    </pre>
                  </div>
                )}

                <textarea
                  className="input-field font-mono text-xs w-full resize-y leading-relaxed"
                  style={{ minHeight: showDiff ? '250px' : 'calc(100vh - 340px)' }}
                  value={content}
                  onChange={(e) => { setContent(e.target.value); setDirty(true); }}
                  spellCheck={false}
                />
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Main Settings Page ───────────────────────────────────────────────────

export function Settings() {
  const [tab, setTab] = useState<'general' | 'keys' | 'playbook'>('general');

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold">Settings</h1>

      <div className="flex gap-1">
        <TabButton label="General" active={tab === 'general'} onClick={() => setTab('general')} />
        <TabButton label="API Keys" active={tab === 'keys'} onClick={() => setTab('keys')} />
        <TabButton label="Playbook" active={tab === 'playbook'} onClick={() => setTab('playbook')} />
      </div>

      {tab === 'general' && <GeneralTab />}
      {tab === 'keys' && <ApiKeysTab />}
      {tab === 'playbook' && <PlaybookTab />}
    </div>
  );
}
