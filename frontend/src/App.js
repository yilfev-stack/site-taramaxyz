import { useState, useEffect, useCallback } from "react";
import "@/App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Severity badge component
const SeverityBadge = ({ severity }) => {
  const colors = {
    Critical: "bg-red-600 text-white",
    High: "bg-orange-500 text-white",
    Medium: "bg-yellow-500 text-black",
    Low: "bg-blue-500 text-white",
  };
  return (
    <span
      className={`px-2 py-1 rounded text-xs font-semibold ${colors[severity] || "bg-gray-500 text-white"}`}
      data-testid={`severity-${severity?.toLowerCase()}`}
    >
      {severity}
    </span>
  );
};

// Issue type badge
const IssueTypeBadge = ({ type }) => {
  const labels = {
    broken_link: "Kırık Link",
    broken_image: "Kırık Görsel",
    language_mismatch: "Dil Uyuşmazlığı",
    redirect_loop: "Redirect Döngüsü",
    wrong_redirect: "Yanlış Yönlendirme",
    mixed_content: "Karışık İçerik",
    missing_alt: "Eksik Alt",
    missing_meta: "Eksik Meta",
    canonical_error: "Canonical Hatası",
    hreflang_error: "Hreflang Hatası",
    content_language_mismatch: "İçerik Dil Hatası",
    broken_anchor: "Kırık Anchor",
    invalid_email: "Geçersiz Email",
    invalid_phone: "Geçersiz Telefon",
    image_content_mismatch: "Görsel-İçerik Uyuşmazlığı",
    large_image: "Büyük Görsel",
    http_in_https: "HTTP/HTTPS Hatası",
    external_link_error: "Harici Link Hatası",
  };
  return (
    <span className="px-2 py-1 rounded text-xs bg-gray-700 text-gray-200" data-testid="issue-type-badge">
      {labels[type] || type}
    </span>
  );
};

// Stats Card
const StatCard = ({ title, value, icon, color = "blue" }) => {
  const colorClasses = {
    blue: "from-blue-500 to-blue-600",
    green: "from-green-500 to-green-600",
    red: "from-red-500 to-red-600",
    orange: "from-orange-500 to-orange-600",
    purple: "from-purple-500 to-purple-600",
    yellow: "from-yellow-500 to-yellow-600",
  };
  return (
    <div
      className={`bg-gradient-to-br ${colorClasses[color]} rounded-xl p-4 text-white shadow-lg`}
      data-testid={`stat-card-${title?.toLowerCase().replace(/\s+/g, "-")}`}
    >
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm opacity-80">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
        </div>
        <div className="text-3xl opacity-80">{icon}</div>
      </div>
    </div>
  );
};

// Progress Bar
const ProgressBar = ({ progress, status }) => {
  const percentage = progress.discovered > 0 ? (progress.crawled / progress.discovered) * 100 : 0;
  return (
    <div className="w-full" data-testid="progress-bar">
      <div className="flex justify-between text-sm mb-2 text-gray-400">
        <span>{progress.message}</span>
        <span>{Math.round(percentage)}%</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-3">
        <div
          className={`h-3 rounded-full transition-all duration-500 ${
            status === "completed"
              ? "bg-green-500"
              : status === "error"
              ? "bg-red-500"
              : "bg-blue-500 animate-pulse"
          }`}
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
      <div className="flex justify-between text-xs mt-2 text-gray-500">
        <span>{progress.crawled} tarandı</span>
        <span>{progress.discovered} keşfedildi</span>
        <span>{progress.issues} sorun</span>
      </div>
    </div>
  );
};

// Issue Row
const IssueRow = ({ issue, index }) => {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className="border-b border-gray-700 hover:bg-gray-800/50 transition-colors"
      data-testid={`issue-row-${index}`}
    >
      <div
        className="p-4 cursor-pointer flex items-center gap-4"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-gray-500 w-8">{index + 1}</span>
        <SeverityBadge severity={issue.severity} />
        <IssueTypeBadge type={issue.issue_type} />
        <span className="text-gray-300 flex-1 truncate">
          {issue.source_url}
        </span>
        <span className="text-gray-500">{issue.source_language}</span>
        <span className={`transform transition-transform ${expanded ? "rotate-180" : ""}`}>
          ▼
        </span>
      </div>
      {expanded && (
        <div className="px-4 pb-4 pl-12 space-y-2 text-sm bg-gray-800/30">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-gray-500">Kaynak URL:</p>
              <a
                href={issue.source_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:underline break-all"
              >
                {issue.source_url}
              </a>
            </div>
            <div>
              <p className="text-gray-500">Hedef URL:</p>
              <a
                href={issue.target_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-400 hover:underline break-all"
              >
                {issue.target_url}
              </a>
            </div>
          </div>
          {issue.element_text && (
            <div>
              <p className="text-gray-500">Element:</p>
              <p className="text-gray-300 bg-gray-700 p-2 rounded mt-1">
                {issue.element_text}
              </p>
            </div>
          )}
          <div className="grid grid-cols-3 gap-4">
            <div>
              <p className="text-gray-500">HTTP Durumu:</p>
              <p className="text-gray-300">{issue.http_status || "N/A"}</p>
            </div>
            <div>
              <p className="text-gray-500">Konum:</p>
              <p className="text-gray-300">{issue.element_location || "N/A"}</p>
            </div>
            <div>
              <p className="text-gray-500">Dil:</p>
              <p className="text-gray-300">{issue.source_language}</p>
            </div>
          </div>
          <div className="bg-yellow-900/30 border border-yellow-700 rounded p-3 mt-2">
            <p className="text-yellow-500 font-semibold">Öneri:</p>
            <p className="text-yellow-200 mt-1">{issue.fix_suggestion}</p>
          </div>
        </div>
      )}
    </div>
  );
};

// URL Row
const URLRow = ({ url, index }) => (
  <div
    className="border-b border-gray-700 p-3 flex items-center gap-4 hover:bg-gray-800/50"
    data-testid={`url-row-${index}`}
  >
    <span className="text-gray-500 w-8 text-sm">{index + 1}</span>
    <span
      className={`px-2 py-1 rounded text-xs font-semibold ${
        url.language === "TR" ? "bg-red-600" : "bg-blue-600"
      } text-white`}
    >
      {url.language}
    </span>
    <span
      className={`px-2 py-1 rounded text-xs ${
        url.http_status === 200
          ? "bg-green-600"
          : url.http_status >= 400
          ? "bg-red-600"
          : "bg-yellow-600"
      } text-white`}
    >
      {url.http_status}
    </span>
    <a
      href={url.url}
      target="_blank"
      rel="noopener noreferrer"
      className="text-blue-400 hover:underline flex-1 truncate"
    >
      {url.url}
    </a>
    <span className="text-gray-400 text-sm truncate max-w-xs">{url.title}</span>
  </div>
);

// Filter Panel
const FilterPanel = ({ filters, setFilters, stats }) => {
  return (
    <div className="bg-gray-800 rounded-lg p-4 mb-4" data-testid="filter-panel">
      <div className="flex flex-wrap gap-4">
        <div>
          <label className="text-gray-400 text-sm block mb-1">Sorun Türü</label>
          <select
            className="bg-gray-700 text-white rounded px-3 py-2 text-sm"
            value={filters.issue_type}
            onChange={(e) => setFilters({ ...filters, issue_type: e.target.value })}
            data-testid="filter-issue-type"
          >
            <option value="">Tümü</option>
            {stats?.by_type &&
              Object.entries(stats.by_type).map(([type, count]) => (
                <option key={type} value={type}>
                  {type} ({count})
                </option>
              ))}
          </select>
        </div>
        <div>
          <label className="text-gray-400 text-sm block mb-1">Önem Derecesi</label>
          <select
            className="bg-gray-700 text-white rounded px-3 py-2 text-sm"
            value={filters.severity}
            onChange={(e) => setFilters({ ...filters, severity: e.target.value })}
            data-testid="filter-severity"
          >
            <option value="">Tümü</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
            <option value="Low">Low</option>
          </select>
        </div>
        <div>
          <label className="text-gray-400 text-sm block mb-1">Dil</label>
          <select
            className="bg-gray-700 text-white rounded px-3 py-2 text-sm"
            value={filters.language}
            onChange={(e) => setFilters({ ...filters, language: e.target.value })}
            data-testid="filter-language"
          >
            <option value="">Tümü</option>
            <option value="TR">Türkçe</option>
            <option value="EN">English</option>
          </select>
        </div>
        <div className="flex items-end">
          <button
            className="bg-gray-600 hover:bg-gray-500 text-white px-4 py-2 rounded text-sm transition-colors"
            onClick={() => setFilters({ issue_type: "", severity: "", language: "" })}
            data-testid="clear-filters-btn"
          >
            Temizle
          </button>
        </div>
      </div>
    </div>
  );
};

// Main App Component
function App() {
  const [activeTab, setActiveTab] = useState("dashboard");
  const [crawlStatus, setCrawlStatus] = useState({
    status: "idle",
    crawled: 0,
    discovered: 0,
    issues: 0,
    message: "",
  });
  const [summary, setSummary] = useState(null);
  const [issues, setIssues] = useState([]);
  const [issuesTotal, setIssuesTotal] = useState(0);
  const [urls, setUrls] = useState([]);
  const [urlsTotal, setUrlsTotal] = useState(0);
  const [stats, setStats] = useState(null);
  const [topIssues, setTopIssues] = useState([]);
  const [filters, setFilters] = useState({ issue_type: "", severity: "", language: "" });
  const [issuePage, setIssuePage] = useState(1);
  const [urlPage, setUrlPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);

  // Fetch status
  const fetchStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/crawl/status`);
      setCrawlStatus(response.data);
    } catch (e) {
      console.error("Status fetch error:", e);
    }
  }, []);

  // Fetch summary
  const fetchSummary = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/report/summary`);
      if (!response.data.error) {
        setSummary(response.data);
      }
    } catch (e) {
      console.error("Summary fetch error:", e);
    }
  }, []);

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/report/stats`);
      setStats(response.data);
    } catch (e) {
      console.error("Stats fetch error:", e);
    }
  }, []);

  // Fetch top issues
  const fetchTopIssues = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/report/top-issues?limit=10`);
      setTopIssues(response.data.issues || []);
    } catch (e) {
      console.error("Top issues fetch error:", e);
    }
  }, []);

  // Fetch issues with filters
  const fetchIssues = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        page: issuePage,
        limit: 50,
        ...(filters.issue_type && { issue_type: filters.issue_type }),
        ...(filters.severity && { severity: filters.severity }),
        ...(filters.language && { language: filters.language }),
      });
      const response = await axios.get(`${API}/report/issues?${params}`);
      setIssues(response.data.issues || []);
      setIssuesTotal(response.data.total || 0);
    } catch (e) {
      console.error("Issues fetch error:", e);
    }
  }, [issuePage, filters]);

  // Fetch URLs
  const fetchUrls = useCallback(async () => {
    try {
      const params = new URLSearchParams({
        page: urlPage,
        limit: 100,
        ...(filters.language && { language: filters.language }),
      });
      const response = await axios.get(`${API}/report/urls?${params}`);
      setUrls(response.data.urls || []);
      setUrlsTotal(response.data.total || 0);
    } catch (e) {
      console.error("URLs fetch error:", e);
    }
  }, [urlPage, filters.language]);

  // Start crawl
  const startCrawl = async () => {
    setLoading(true);
    try {
      await axios.post(`${API}/crawl/start`, {
        target_url: "https://www.demart.com.tr",
        max_concurrent: 5,
      });
      setCrawlStatus({ ...crawlStatus, status: "starting", message: "Tarama başlatılıyor..." });
    } catch (e) {
      console.error("Start crawl error:", e);
      alert("Tarama başlatılamadı!");
    }
    setLoading(false);
  };

  // Stop crawl
  const stopCrawl = async () => {
    try {
      await axios.post(`${API}/crawl/stop`);
    } catch (e) {
      console.error("Stop crawl error:", e);
    }
  };

  // Export CSV
  const exportCSV = async () => {
    window.open(`${API}/report/export/csv`, "_blank");
  };

  // Export JSON
  const exportJSON = async () => {
    window.open(`${API}/report/export/json`, "_blank");
  };

  // WebSocket connection
  useEffect(() => {
    const wsUrl = BACKEND_URL.replace("https://", "wss://").replace("http://", "ws://");
    let ws;
    let reconnectTimeout;

    const connect = () => {
      ws = new WebSocket(`${wsUrl}/api/ws/progress`);

      ws.onopen = () => {
        setWsConnected(true);
        console.log("WebSocket connected");
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setCrawlStatus(data);
          if (data.status === "completed") {
            fetchSummary();
            fetchStats();
            fetchTopIssues();
            fetchIssues();
          }
        } catch (e) {
          console.error("WS message error:", e);
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        reconnectTimeout = setTimeout(connect, 3000);
      };

      ws.onerror = () => {
        ws.close();
      };
    };

    connect();

    return () => {
      clearTimeout(reconnectTimeout);
      if (ws) ws.close();
    };
  }, [fetchSummary, fetchStats, fetchTopIssues, fetchIssues]);

  // Initial data fetch
  useEffect(() => {
    fetchStatus();
    fetchSummary();
    fetchStats();
    fetchTopIssues();
  }, [fetchStatus, fetchSummary, fetchStats, fetchTopIssues]);

  // Fetch issues when tab changes or filters change
  useEffect(() => {
    if (activeTab === "issues") {
      fetchIssues();
    }
  }, [activeTab, fetchIssues]);

  // Fetch URLs when tab changes
  useEffect(() => {
    if (activeTab === "urls") {
      fetchUrls();
    }
  }, [activeTab, fetchUrls]);

  // Polling for status when crawl is running
  useEffect(() => {
    if (!wsConnected && ["running", "starting"].includes(crawlStatus.status)) {
      const interval = setInterval(fetchStatus, 2000);
      return () => clearInterval(interval);
    }
  }, [wsConnected, crawlStatus.status, fetchStatus]);

  return (
    <div className="min-h-screen bg-gray-900 text-white" data-testid="app-container">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 shadow-lg" data-testid="header">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="bg-gradient-to-br from-blue-500 to-purple-600 p-2 rounded-lg">
                <svg className="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold">DEMART.COM.TR</h1>
                <p className="text-gray-400 text-sm">Web Sitesi Denetim Aracı</p>
              </div>
            </div>
            <div className="flex items-center gap-4">
              <div className={`flex items-center gap-2 text-sm ${wsConnected ? "text-green-400" : "text-red-400"}`}>
                <span className={`w-2 h-2 rounded-full ${wsConnected ? "bg-green-400" : "bg-red-400"}`}></span>
                {wsConnected ? "Bağlı" : "Bağlantı Yok"}
              </div>
              {crawlStatus.status === "running" ? (
                <button
                  onClick={stopCrawl}
                  className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg font-semibold transition-colors"
                  data-testid="stop-crawl-btn"
                >
                  ⏹ Durdur
                </button>
              ) : (
                <button
                  onClick={startCrawl}
                  disabled={loading || crawlStatus.status === "starting"}
                  className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold transition-colors"
                  data-testid="start-crawl-btn"
                >
                  {loading ? "✱ Başlatılıyor..." : "▶ Taramayı Başlat"}
                </button>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Progress Bar */}
      {["running", "starting", "completed", "stopped", "error"].includes(crawlStatus.status) && (
        <div className="bg-gray-800 border-b border-gray-700 px-4 py-4">
          <div className="container mx-auto">
            <ProgressBar progress={crawlStatus} status={crawlStatus.status} />
          </div>
        </div>
      )}

      {/* Tabs */}
      <nav className="bg-gray-800 border-b border-gray-700" data-testid="navigation-tabs">
        <div className="container mx-auto px-4">
          <div className="flex gap-1">
            {[
              { id: "dashboard", label: "📊 Dashboard", icon: "" },
              { id: "issues", label: "⚠️ Sorunlar", count: issuesTotal || summary?.total_issues },
              { id: "urls", label: "🔗 URL'ler", count: urlsTotal || summary?.total_urls },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 font-medium transition-colors relative ${
                  activeTab === tab.id
                    ? "text-blue-400 border-b-2 border-blue-400"
                    : "text-gray-400 hover:text-white"
                }`}
                data-testid={`tab-${tab.id}`}
              >
                {tab.label}
                {tab.count > 0 && (
                  <span className="ml-2 bg-gray-700 px-2 py-0.5 rounded-full text-xs">
                    {tab.count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        {/* Dashboard Tab */}
        {activeTab === "dashboard" && (
          <div className="space-y-6" data-testid="dashboard-content">
            {/* Summary Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              <StatCard title="Toplam URL" value={summary?.total_urls || 0} icon="🔗" color="blue" />
              <StatCard title="TR Sayfalar" value={summary?.tr_pages || 0} icon="🇹🇷" color="red" />
              <StatCard title="EN Sayfalar" value={summary?.en_pages || 0} icon="🇬🇧" color="purple" />
              <StatCard title="Kırık Link" value={summary?.broken_links || 0} icon="🔗" color="orange" />
              <StatCard title="Kırık Görsel" value={summary?.broken_images || 0} icon="🖼️" color="yellow" />
              <StatCard title="Dil Hataları" value={summary?.language_errors || 0} icon="🌐" color="red" />
            </div>

            {/* Severity Summary */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-gray-800 rounded-xl p-6" data-testid="severity-summary">
                <h3 className="text-lg font-semibold mb-4">Önem Derecesine Göre Sorunlar</h3>
                <div className="space-y-3">
                  {[
                    { label: "Critical", value: summary?.critical_issues || 0, color: "bg-red-600" },
                    { label: "High", value: summary?.high_issues || 0, color: "bg-orange-500" },
                    { label: "Medium", value: summary?.medium_issues || 0, color: "bg-yellow-500" },
                    { label: "Low", value: summary?.low_issues || 0, color: "bg-blue-500" },
                  ].map((item) => (
                    <div key={item.label} className="flex items-center gap-3">
                      <span className={`${item.color} w-3 h-3 rounded-full`}></span>
                      <span className="text-gray-300 flex-1">{item.label}</span>
                      <span className="font-semibold">{item.value}</span>
                      <div className="w-32 bg-gray-700 rounded-full h-2">
                        <div
                          className={`${item.color} h-2 rounded-full`}
                          style={{
                            width: `${summary?.total_issues ? (item.value / summary.total_issues) * 100 : 0}%`,
                          }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Issue Type Distribution */}
              <div className="bg-gray-800 rounded-xl p-6" data-testid="issue-type-distribution">
                <h3 className="text-lg font-semibold mb-4">Sorun Türü Dağılımı</h3>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {stats?.by_type &&
                    Object.entries(stats.by_type)
                      .sort((a, b) => b[1] - a[1])
                      .map(([type, count]) => (
                        <div key={type} className="flex items-center gap-2">
                          <IssueTypeBadge type={type} />
                          <span className="flex-1"></span>
                          <span className="text-gray-400">{count}</span>
                        </div>
                      ))}
                </div>
              </div>
            </div>

            {/* Top 10 Critical Issues */}
            <div className="bg-gray-800 rounded-xl p-6" data-testid="top-issues-section">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">En Kritik 10 Sorun</h3>
                <div className="flex gap-2">
                  <button
                    onClick={exportCSV}
                    className="bg-green-600 hover:bg-green-700 text-white px-3 py-1 rounded text-sm transition-colors"
                    data-testid="export-csv-btn"
                  >
                    📄 CSV İndir
                  </button>
                  <button
                    onClick={exportJSON}
                    className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded text-sm transition-colors"
                    data-testid="export-json-btn"
                  >
                    📄 JSON İndir
                  </button>
                </div>
              </div>
              <div className="border border-gray-700 rounded-lg overflow-hidden">
                {topIssues.length > 0 ? (
                  topIssues.map((issue, index) => (
                    <IssueRow key={index} issue={issue} index={index} />
                  ))
                ) : (
                  <div className="p-8 text-center text-gray-500">
                    <p>Henüz sorun bulunamadı. Taramayı başlatın.</p>
                  </div>
                )}
              </div>
            </div>

            {/* Crawl Info */}
            {summary && (
              <div className="bg-gray-800 rounded-xl p-6" data-testid="crawl-info">
                <h3 className="text-lg font-semibold mb-4">Tarama Bilgisi</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                  <div>
                    <p className="text-gray-500">Domain</p>
                    <p className="text-gray-200">{summary.domain}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Başlangıç</p>
                    <p className="text-gray-200">{new Date(summary.start_time).toLocaleString("tr-TR")}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Bitiş</p>
                    <p className="text-gray-200">{new Date(summary.end_time).toLocaleString("tr-TR")}</p>
                  </div>
                  <div>
                    <p className="text-gray-500">Toplam Sorun</p>
                    <p className="text-gray-200">{summary.total_issues}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Issues Tab */}
        {activeTab === "issues" && (
          <div className="space-y-4" data-testid="issues-content">
            <FilterPanel filters={filters} setFilters={setFilters} stats={stats} />

            <div className="flex items-center justify-between">
              <p className="text-gray-400">Toplam {issuesTotal} sorun</p>
              <div className="flex gap-2">
                <button
                  onClick={() => setIssuePage(Math.max(1, issuePage - 1))}
                  disabled={issuePage === 1}
                  className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 px-3 py-1 rounded text-sm"
                  data-testid="prev-page-btn"
                >
                  « Önceki
                </button>
                <span className="px-3 py-1 text-gray-400">Sayfa {issuePage}</span>
                <button
                  onClick={() => setIssuePage(issuePage + 1)}
                  disabled={issues.length < 50}
                  className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 px-3 py-1 rounded text-sm"
                  data-testid="next-page-btn"
                >
                  Sonraki »
                </button>
              </div>
            </div>

            <div className="bg-gray-800 rounded-xl overflow-hidden border border-gray-700">
              {issues.length > 0 ? (
                issues.map((issue, index) => (
                  <IssueRow key={index} issue={issue} index={(issuePage - 1) * 50 + index} />
                ))
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <p>Filtrelere uygun sorun bulunamadı.</p>
                </div>
              )}
            </div>
          </div>
        )}

        {/* URLs Tab */}
        {activeTab === "urls" && (
          <div className="space-y-4" data-testid="urls-content">
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="flex items-center gap-4">
                <div>
                  <label className="text-gray-400 text-sm block mb-1">Dil Filtresi</label>
                  <select
                    className="bg-gray-700 text-white rounded px-3 py-2 text-sm"
                    value={filters.language}
                    onChange={(e) => setFilters({ ...filters, language: e.target.value })}
                    data-testid="url-language-filter"
                  >
                    <option value="">Tümü</option>
                    <option value="TR">Türkçe</option>
                    <option value="EN">English</option>
                  </select>
                </div>
              </div>
            </div>

            <div className="flex items-center justify-between">
              <p className="text-gray-400">Toplam {urlsTotal} URL</p>
              <div className="flex gap-2">
                <button
                  onClick={() => setUrlPage(Math.max(1, urlPage - 1))}
                  disabled={urlPage === 1}
                  className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 px-3 py-1 rounded text-sm"
                  data-testid="urls-prev-page-btn"
                >
                  « Önceki
                </button>
                <span className="px-3 py-1 text-gray-400">Sayfa {urlPage}</span>
                <button
                  onClick={() => setUrlPage(urlPage + 1)}
                  disabled={urls.length < 100}
                  className="bg-gray-700 hover:bg-gray-600 disabled:opacity-50 px-3 py-1 rounded text-sm"
                  data-testid="urls-next-page-btn"
                >
                  Sonraki »
                </button>
              </div>
            </div>

            <div className="bg-gray-800 rounded-xl overflow-hidden border border-gray-700">
              {urls.length > 0 ? (
                urls.map((url, index) => (
                  <URLRow key={index} url={url} index={(urlPage - 1) * 100 + index} />
                ))
              ) : (
                <div className="p-8 text-center text-gray-500">
                  <p>Henüz URL bulunamadı. Taramayı başlatın.</p>
                </div>
              )}
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 py-4 mt-8" data-testid="footer">
        <div className="container mx-auto px-4 text-center text-gray-500 text-sm">
          <p>DEMART.COM.TR Web Sitesi Denetim Aracı - %100 Link, Dil, İçerik Uyumluluk Testi</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
