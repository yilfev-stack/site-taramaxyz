import { useState, useEffect, useCallback } from "react";
import "@/App.css";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "http://localhost:8001";
const API = `${BACKEND_URL}/api`;

// Stat Card
const StatCard = ({ title, value, icon, color = "blue" }) => {
  const colors = {
    blue: "from-blue-500 to-blue-600",
    green: "from-green-500 to-green-600",
    red: "from-red-500 to-red-600",
    purple: "from-purple-500 to-purple-600",
    yellow: "from-yellow-500 to-yellow-600",
    pink: "from-pink-500 to-pink-600",
  };
  return (
    <div className={`bg-gradient-to-br ${colors[color]} rounded-xl p-4 text-white shadow-lg`}>
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
    <div className="w-full">
      <div className="flex justify-between text-sm mb-2 text-gray-400">
        <span>{progress.message}</span>
        <span>{Math.round(percentage)}%</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-3">
        <div
          className={`h-3 rounded-full transition-all duration-500 ${
            status === "completed" ? "bg-green-500" : status === "error" ? "bg-red-500" : "bg-blue-500"
          }`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        ></div>
      </div>
      <div className="flex justify-between text-xs mt-2 text-gray-500">
        <span>{progress.crawled} tarandı</span>
        <span>{progress.images || 0} görsel</span>
        <span>{progress.videos || 0} video</span>
      </div>
    </div>
  );
};

// Image Card with selection
const ImageCard = ({ image, selected, onToggle }) => (
  <div
    className={`relative group cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
      selected ? "border-blue-500 ring-2 ring-blue-500" : "border-gray-700 hover:border-gray-500"
    }`}
    onClick={onToggle}
  >
    <img
      src={image.url}
      alt={image.alt || "Image"}
      className="w-full h-40 object-cover"
      onError={(e) => { e.target.src = "https://via.placeholder.com/300x200?text=Yüklenemedi"; }}
    />
    <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-all flex items-center justify-center">
      <span className={`text-white text-2xl ${selected ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}>
        {selected ? "✓" : "+"}
      </span>
    </div>
    {image.size_kb > 0 && (
      <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-70 text-white text-xs p-1 text-center">
        {image.size_kb.toFixed(0)} KB
      </div>
    )}
  </div>
);

// Video Card with selection
const VideoCard = ({ video, selected, onToggle }) => (
  <div
    className={`relative group cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
      selected ? "border-blue-500 ring-2 ring-blue-500" : "border-gray-700 hover:border-gray-500"
    }`}
    onClick={onToggle}
  >
    <div className="w-full h-40 bg-gray-800 flex items-center justify-center">
      <span className="text-4xl">🎬</span>
    </div>
    <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-all flex items-center justify-center">
      <span className={`text-white text-2xl ${selected ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}>
        {selected ? "✓" : "+"}
      </span>
    </div>
    <div className="absolute bottom-0 left-0 right-0 bg-black bg-opacity-70 text-white text-xs p-2">
      <p className="truncate">{video.type.toUpperCase()}</p>
    </div>
  </div>
);

// Text Card with selection
const TextCard = ({ text, selected, onToggle }) => (
  <div
    className={`p-4 rounded-lg cursor-pointer border-2 transition-all ${
      selected ? "border-blue-500 bg-blue-900/20" : "border-gray-700 hover:border-gray-500 bg-gray-800"
    }`}
    onClick={onToggle}
  >
    <div className="flex items-start gap-3">
      <span className={`text-xl ${selected ? "text-blue-400" : "text-gray-400"}`}>
        {selected ? "✓" : "📝"}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-gray-400 mb-1">{text.type} - {text.word_count} kelime</p>
        <p className="text-gray-200 text-sm line-clamp-3">{text.content}</p>
      </div>
    </div>
  </div>
);

// Main App
function App() {
  const [targetUrl, setTargetUrl] = useState("");
  const [maxPages, setMaxPages] = useState(50);
  const [activeTab, setActiveTab] = useState("images");
  const [crawlStatus, setCrawlStatus] = useState({ status: "idle", crawled: 0, discovered: 0, issues: 0, message: "" });
  const [summary, setSummary] = useState(null);
  const [images, setImages] = useState([]);
  const [videos, setVideos] = useState([]);
  const [texts, setTexts] = useState([]);
  const [issues, setIssues] = useState([]);
  const [selectedImages, setSelectedImages] = useState(new Set());
  const [selectedVideos, setSelectedVideos] = useState(new Set());
  const [selectedTexts, setSelectedTexts] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Fetch data
  const fetchSummary = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/report/summary`);
      if (!response.data.error) setSummary(response.data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchImages = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/report/images?limit=200`);
      setImages(response.data.images || []);
    } catch (e) { console.error(e); }
  }, []);

  const fetchVideos = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/report/videos?limit=100`);
      setVideos(response.data.videos || []);
    } catch (e) { console.error(e); }
  }, []);

  const fetchTexts = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/report/texts?limit=100`);
      setTexts(response.data.texts || []);
    } catch (e) { console.error(e); }
  }, []);

  const fetchIssues = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/report/issues?limit=100`);
      setIssues(response.data.issues || []);
    } catch (e) { console.error(e); }
  }, []);

  const fetchStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API}/crawl/status`);
      setCrawlStatus(response.data);
    } catch (e) { console.error(e); }
  }, []);

  // Start crawl
  const startCrawl = async () => {
    if (!targetUrl) {
      alert("Lütfen bir web sitesi URL'si girin!");
      return;
    }
    
    setLoading(true);
    setSelectedImages(new Set());
    setSelectedVideos(new Set());
    setSelectedTexts(new Set());
    
    try {
      let url = targetUrl;
      if (!url.startsWith("http")) url = "https://" + url;
      
      await axios.post(`${API}/crawl/start`, {
        target_url: url,
        max_concurrent: 5,
        max_pages: maxPages,
        enable_ai_image_analysis: false
      });
      setCrawlStatus({ ...crawlStatus, status: "starting", message: "Tarama başlatılıyor..." });
    } catch (e) {
      console.error(e);
      alert("Tarama başlatılamadı!");
    }
    setLoading(false);
  };

  // Stop crawl
  const stopCrawl = async () => {
    try {
      await axios.post(`${API}/crawl/stop`);
    } catch (e) { console.error(e); }
  };

  // Download selected items
  const downloadSelected = async (type) => {
    let urls = [];
    
    if (type === "images") {
      urls = Array.from(selectedImages);
    } else if (type === "videos") {
      urls = Array.from(selectedVideos);
    } else if (type === "all") {
      urls = [...Array.from(selectedImages), ...Array.from(selectedVideos)];
    }
    
    if (urls.length === 0) {
      alert("Lütfen indirmek için öğe seçin!");
      return;
    }
    
    setDownloading(true);
    
    try {
      const response = await axios.post(`${API}/download/start`, {
        urls: urls,
        download_type: type
      });
      
      if (response.data.success) {
        // Download the zip file
        window.open(`${API}/download/file/${response.data.download_id}`, "_blank");
        alert(`${response.data.files_count} dosya indirildi!`);
      } else {
        alert("İndirme başarısız: " + response.data.message);
      }
    } catch (e) {
      console.error(e);
      alert("İndirme hatası!");
    }
    
    setDownloading(false);
  };

  // Copy text to clipboard
  const copySelectedTexts = () => {
    const selectedTextContents = texts
      .filter(t => selectedTexts.has(t.content))
      .map(t => t.content)
      .join("\n\n---\n\n");
    
    navigator.clipboard.writeText(selectedTextContents);
    alert("Metinler panoya kopyalandı!");
  };

  // Select all / none
  const selectAllImages = () => {
    if (selectedImages.size === images.length) {
      setSelectedImages(new Set());
    } else {
      setSelectedImages(new Set(images.map(img => img.url)));
    }
  };

  const selectAllVideos = () => {
    if (selectedVideos.size === videos.length) {
      setSelectedVideos(new Set());
    } else {
      setSelectedVideos(new Set(videos.map(vid => vid.url)));
    }
  };

  const selectAllTexts = () => {
    if (selectedTexts.size === texts.length) {
      setSelectedTexts(new Set());
    } else {
      setSelectedTexts(new Set(texts.map(txt => txt.content)));
    }
  };

  // Polling
  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 2000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  useEffect(() => {
    if (crawlStatus.status === "completed") {
      fetchSummary();
      fetchImages();
      fetchVideos();
      fetchTexts();
      fetchIssues();
    }
  }, [crawlStatus.status, fetchSummary, fetchImages, fetchVideos, fetchTexts, fetchIssues]);

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 shadow-lg">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="bg-gradient-to-br from-green-500 to-blue-600 p-2 rounded-lg">
                <span className="text-2xl">🔍</span>
              </div>
              <div>
                <h1 className="text-xl font-bold">Web Sitesi Tarama Aracı</h1>
                <p className="text-gray-400 text-sm">Görsel, Video ve Metin Toplayıcı</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* URL Input Section */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 py-6">
        <div className="container mx-auto">
          <div className="flex flex-col md:flex-row gap-4 items-end">
            <div className="flex-1">
              <label className="block text-gray-400 text-sm mb-2">Web Sitesi URL'si</label>
              <input
                type="text"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder="örn: www.example.com"
                className="w-full bg-gray-700 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none"
                disabled={crawlStatus.status === "running"}
              />
            </div>
            <div className="w-32">
              <label className="block text-gray-400 text-sm mb-2">Max Sayfa</label>
              <input
                type="number"
                value={maxPages}
                onChange={(e) => setMaxPages(parseInt(e.target.value) || 50)}
                min="1"
                max="500"
                className="w-full bg-gray-700 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none"
                disabled={crawlStatus.status === "running"}
              />
            </div>
            <div>
              {crawlStatus.status === "running" ? (
                <button
                  onClick={stopCrawl}
                  className="bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-lg font-semibold transition-colors"
                >
                  ⏹ Durdur
                </button>
              ) : (
                <button
                  onClick={startCrawl}
                  disabled={loading}
                  className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg font-semibold transition-colors"
                >
                  {loading ? "⏳ Başlatılıyor..." : "🚀 Taramayı Başlat"}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Progress Bar */}
      {["running", "starting", "completed", "stopped", "error"].includes(crawlStatus.status) && (
        <div className="bg-gray-800 border-b border-gray-700 px-4 py-4">
          <div className="container mx-auto">
            <ProgressBar progress={crawlStatus} status={crawlStatus.status} />
          </div>
        </div>
      )}

      {/* Stats */}
      {summary && (
        <div className="container mx-auto px-4 py-6">
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
            <StatCard title="Taranan Sayfa" value={summary.total_urls || 0} icon="📄" color="blue" />
            <StatCard title="Görseller" value={summary.total_images || 0} icon="🖼️" color="green" />
            <StatCard title="Videolar" value={summary.total_videos || 0} icon="🎬" color="purple" />
            <StatCard title="Metinler" value={summary.total_texts || 0} icon="📝" color="yellow" />
            <StatCard title="Sorunlar" value={summary.issues_count || 0} icon="⚠️" color="red" />
            <StatCard title="Domain" value={summary.domain?.substring(0, 15) || "-"} icon="🌐" color="pink" />
          </div>
        </div>
      )}

      {/* Tabs */}
      <nav className="bg-gray-800 border-b border-gray-700">
        <div className="container mx-auto px-4">
          <div className="flex gap-1">
            {[
              { id: "images", label: "🖼️ Görseller", count: images.length },
              { id: "videos", label: "🎬 Videolar", count: videos.length },
              { id: "texts", label: "📝 Metinler", count: texts.length },
              { id: "issues", label: "⚠️ Sorunlar", count: issues.length },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 font-medium transition-colors relative ${
                  activeTab === tab.id
                    ? "text-blue-400 border-b-2 border-blue-400"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {tab.label}
                {tab.count > 0 && (
                  <span className="ml-2 bg-gray-700 px-2 py-0.5 rounded-full text-xs">{tab.count}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="container mx-auto px-4 py-6">
        {/* Images Tab */}
        {activeTab === "images" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button
                  onClick={selectAllImages}
                  className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg text-sm"
                >
                  {selectedImages.size === images.length ? "Seçimi Kaldır" : "Tümünü Seç"}
                </button>
                <span className="text-gray-400">{selectedImages.size} seçili</span>
              </div>
              <button
                onClick={() => downloadSelected("images")}
                disabled={selectedImages.size === 0 || downloading}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold"
              >
                {downloading ? "⏳ İndiriliyor..." : `📥 Seçilenleri İndir (${selectedImages.size})`}
              </button>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {images.map((image, index) => (
                <ImageCard
                  key={index}
                  image={image}
                  selected={selectedImages.has(image.url)}
                  onToggle={() => {
                    const newSelected = new Set(selectedImages);
                    if (newSelected.has(image.url)) {
                      newSelected.delete(image.url);
                    } else {
                      newSelected.add(image.url);
                    }
                    setSelectedImages(newSelected);
                  }}
                />
              ))}
            </div>
            
            {images.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <p className="text-4xl mb-4">🖼️</p>
                <p>Henüz görsel bulunamadı. Önce bir web sitesi tarayın.</p>
              </div>
            )}
          </div>
        )}

        {/* Videos Tab */}
        {activeTab === "videos" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button
                  onClick={selectAllVideos}
                  className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg text-sm"
                >
                  {selectedVideos.size === videos.length ? "Seçimi Kaldır" : "Tümünü Seç"}
                </button>
                <span className="text-gray-400">{selectedVideos.size} seçili</span>
              </div>
              <button
                onClick={() => downloadSelected("videos")}
                disabled={selectedVideos.size === 0 || downloading}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold"
              >
                {downloading ? "⏳ İndiriliyor..." : `📥 Seçilenleri İndir (${selectedVideos.size})`}
              </button>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {videos.map((video, index) => (
                <VideoCard
                  key={index}
                  video={video}
                  selected={selectedVideos.has(video.url)}
                  onToggle={() => {
                    const newSelected = new Set(selectedVideos);
                    if (newSelected.has(video.url)) {
                      newSelected.delete(video.url);
                    } else {
                      newSelected.add(video.url);
                    }
                    setSelectedVideos(newSelected);
                  }}
                />
              ))}
            </div>
            
            {videos.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <p className="text-4xl mb-4">🎬</p>
                <p>Henüz video bulunamadı.</p>
              </div>
            )}
          </div>
        )}

        {/* Texts Tab */}
        {activeTab === "texts" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <button
                  onClick={selectAllTexts}
                  className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg text-sm"
                >
                  {selectedTexts.size === texts.length ? "Seçimi Kaldır" : "Tümünü Seç"}
                </button>
                <span className="text-gray-400">{selectedTexts.size} seçili</span>
              </div>
              <button
                onClick={copySelectedTexts}
                disabled={selectedTexts.size === 0}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold"
              >
                📋 Seçilenleri Kopyala ({selectedTexts.size})
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {texts.map((text, index) => (
                <TextCard
                  key={index}
                  text={text}
                  selected={selectedTexts.has(text.content)}
                  onToggle={() => {
                    const newSelected = new Set(selectedTexts);
                    if (newSelected.has(text.content)) {
                      newSelected.delete(text.content);
                    } else {
                      newSelected.add(text.content);
                    }
                    setSelectedTexts(newSelected);
                  }}
                />
              ))}
            </div>
            
            {texts.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <p className="text-4xl mb-4">📝</p>
                <p>Henüz metin bulunamadı.</p>
              </div>
            )}
          </div>
        )}

        {/* Issues Tab */}
        {activeTab === "issues" && (
          <div className="space-y-4">
            {issues.map((issue, index) => (
              <div key={index} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <div className="flex items-start gap-3">
                  <span className={`px-2 py-1 rounded text-xs font-semibold ${
                    issue.severity === "Critical" ? "bg-red-600" :
                    issue.severity === "High" ? "bg-orange-500" :
                    "bg-yellow-500"
                  } text-white`}>
                    {issue.severity}
                  </span>
                  <div className="flex-1">
                    <p className="text-gray-300">{issue.issue_type}</p>
                    <p className="text-gray-500 text-sm mt-1 truncate">{issue.source_url}</p>
                    <p className="text-yellow-400 text-sm mt-2">{issue.fix_suggestion}</p>
                  </div>
                </div>
              </div>
            ))}
            
            {issues.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <p className="text-4xl mb-4">✅</p>
                <p>Sorun bulunamadı!</p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 py-4 mt-8">
        <div className="container mx-auto px-4 text-center text-gray-500 text-sm">
          <p>Web Sitesi Tarama ve İçerik Toplama Aracı</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
