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
        />
      </div>
    </div>
  );
};

// Image Card
const ImageCard = ({ image, selected, onToggle }) => (
  <div
    className={`relative group cursor-pointer rounded-lg overflow-hidden border-2 transition-all ${
      selected ? "border-green-500 ring-2 ring-green-500" : "border-gray-700 hover:border-gray-500"
    }`}
    onClick={onToggle}
  >
    <img
      src={image.url}
      alt={image.title || "Image"}
      className="w-full h-40 object-cover"
      onError={(e) => { e.target.src = "https://via.placeholder.com/300x200?text=X"; }}
    />
    <div className="absolute inset-0 bg-black bg-opacity-0 group-hover:bg-opacity-50 transition-all flex items-center justify-center">
      <span className={`text-white text-3xl font-bold ${selected ? "opacity-100" : "opacity-0 group-hover:opacity-100"}`}>
        {selected ? "✓" : "+"}
      </span>
    </div>
  </div>
);

// YouTube Card
const YouTubeCard = ({ video, onDownload, downloading }) => (
  <div className="bg-gray-800 rounded-lg overflow-hidden border border-gray-700">
    <div className="relative">
      <img
        src={video.thumbnail}
        alt={video.title}
        className="w-full h-40 object-cover"
        onError={(e) => { e.target.src = "https://via.placeholder.com/300x200?text=YouTube"; }}
      />
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-6xl opacity-80">▶</span>
      </div>
    </div>
    <div className="p-3">
      <p className="text-sm text-gray-300 truncate mb-2">{video.title || video.url}</p>
      <div className="flex gap-2">
        <button
          onClick={() => onDownload(video.url, "video")}
          disabled={downloading}
          className="flex-1 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white px-2 py-1.5 rounded text-xs font-semibold"
        >
          {downloading ? "⏳" : "📹"} Video
        </button>
        <button
          onClick={() => onDownload(video.url, "audio")}
          disabled={downloading}
          className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 text-white px-2 py-1.5 rounded text-xs font-semibold"
        >
          {downloading ? "⏳" : "🎵"} MP3
        </button>
      </div>
    </div>
  </div>
);

// Direct Video Downloader Component
const DirectVideoDownloader = ({ onDownloadComplete }) => {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [videoInfo, setVideoInfo] = useState(null);
  const [downloading, setDownloading] = useState(false);

  const checkVideo = async () => {
    if (!url) return;
    setLoading(true);
    setVideoInfo(null);
    try {
      const res = await axios.get(`${API}/video/info?url=${encodeURIComponent(url)}`);
      if (res.data.success) {
        setVideoInfo(res.data.info);
      } else {
        alert("Video bulunamadı: " + res.data.message);
      }
    } catch (e) {
      alert("Hata: " + e.message);
    }
    setLoading(false);
  };

  const downloadVideo = async (format) => {
    setDownloading(true);
    try {
      const res = await axios.post(`${API}/download/video`, { url, format });
      if (res.data.success) {
        window.open(`${API}/download/youtube-file/${res.data.filename}`, "_blank");
        alert(`İndirildi: ${res.data.title}`);
        if (onDownloadComplete) onDownloadComplete();
      } else {
        alert("İndirme başarısız: " + res.data.message);
      }
    } catch (e) {
      alert("Hata: " + e.message);
    }
    setDownloading(false);
  };

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700 mb-6">
      <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
        <span>🎬</span> Direkt Video İndir
        <span className="text-xs text-gray-500 font-normal">(VK, TikTok, Twitter, Instagram, Facebook...)</span>
      </h3>
      
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Video URL yapıştır (örn: vk.com/video...)"
          className="flex-1 bg-gray-700 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none"
        />
        <button
          onClick={checkVideo}
          disabled={loading || !url}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg font-semibold"
        >
          {loading ? "⏳ Kontrol..." : "🔍 Kontrol Et"}
        </button>
      </div>

      {videoInfo && (
        <div className="bg-gray-700 rounded-lg p-4">
          <div className="flex gap-4">
            {videoInfo.thumbnail && (
              <img src={videoInfo.thumbnail} alt="" className="w-32 h-20 object-cover rounded" />
            )}
            <div className="flex-1">
              <p className="font-semibold text-white">{videoInfo.title}</p>
              <p className="text-gray-400 text-sm">{videoInfo.uploader}</p>
              {videoInfo.duration > 0 && (
                <p className="text-gray-500 text-xs">Süre: {Math.floor(videoInfo.duration / 60)}:{(videoInfo.duration % 60).toString().padStart(2, '0')}</p>
              )}
            </div>
          </div>
          <div className="flex gap-3 mt-4">
            <button
              onClick={() => downloadVideo("video")}
              disabled={downloading}
              className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold"
            >
              {downloading ? "⏳ İndiriliyor..." : "📹 Video İndir"}
            </button>
            <button
              onClick={() => downloadVideo("audio")}
              disabled={downloading}
              className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold"
            >
              {downloading ? "⏳ İndiriliyor..." : "🎵 Ses İndir (MP3)"}
            </button>
          </div>
        </div>
      )}

      <div className="mt-4 text-xs text-gray-500">
        <p className="font-semibold mb-1">Desteklenen siteler:</p>
        <p>YouTube, VK, TikTok, Twitter/X, Instagram, Facebook, Dailymotion, Vimeo, Twitch, Reddit, ve 1000+ site...</p>
      </div>
    </div>
  );
};

// Text Card
const TextCard = ({ text, selected, onToggle }) => (
  <div
    className={`p-4 rounded-lg cursor-pointer border-2 transition-all ${
      selected ? "border-green-500 bg-green-900/20" : "border-gray-700 hover:border-gray-500 bg-gray-800"
    }`}
    onClick={onToggle}
  >
    <div className="flex items-start gap-3">
      <span className={`text-xl ${selected ? "text-green-400" : "text-gray-400"}`}>
        {selected ? "✓" : "📝"}
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-xs text-gray-500 mb-1">{text.type?.toUpperCase()} • {text.word_count} kelime</p>
        <p className="text-gray-200 text-sm">{text.content}</p>
      </div>
    </div>
  </div>
);

// Main App
function App() {
  const [targetUrl, setTargetUrl] = useState("");
  const [maxPages, setMaxPages] = useState(30);
  const [activeTab, setActiveTab] = useState("images");
  const [crawlStatus, setCrawlStatus] = useState({ status: "idle", crawled: 0, discovered: 0, images: 0, videos: 0, message: "" });
  const [summary, setSummary] = useState(null);
  const [images, setImages] = useState([]);
  const [videos, setVideos] = useState({ videos: [], youtube: [] });
  const [texts, setTexts] = useState([]);
  const [issues, setIssues] = useState([]);
  const [selectedImages, setSelectedImages] = useState(new Set());
  const [selectedTexts, setSelectedTexts] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [ytDownloading, setYtDownloading] = useState(false);

  // Fetch functions
  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/crawl/status`);
      setCrawlStatus(res.data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchSummary = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/report/summary`);
      if (!res.data.error) setSummary(res.data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchImages = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/report/images?limit=200`);
      setImages(res.data.images || []);
    } catch (e) { console.error(e); }
  }, []);

  const fetchVideos = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/report/videos`);
      setVideos(res.data);
    } catch (e) { console.error(e); }
  }, []);

  const fetchTexts = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/report/texts?limit=100`);
      setTexts(res.data.texts || []);
    } catch (e) { console.error(e); }
  }, []);

  const fetchIssues = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/report/issues`);
      setIssues(res.data.issues || []);
    } catch (e) { console.error(e); }
  }, []);

  // Start crawl
  const startCrawl = async () => {
    if (!targetUrl) {
      alert("URL girin!");
      return;
    }
    setLoading(true);
    setSelectedImages(new Set());
    setSelectedTexts(new Set());
    
    try {
      await axios.post(`${API}/crawl/start`, { target_url: targetUrl, max_pages: maxPages });
      setCrawlStatus({ ...crawlStatus, status: "starting", message: "Başlatılıyor..." });
    } catch (e) {
      alert("Hata: " + e.message);
    }
    setLoading(false);
  };

  // Stop crawl
  const stopCrawl = async () => {
    try { await axios.post(`${API}/crawl/stop`); } catch (e) { console.error(e); }
  };

  // Download images
  const downloadImages = async () => {
    if (selectedImages.size === 0) {
      alert("Görsel seçin!");
      return;
    }
    setDownloading(true);
    try {
      const res = await axios.post(`${API}/download/images`, { urls: Array.from(selectedImages) });
      if (res.data.success) {
        window.open(`${API}/download/file/${res.data.download_id}`, "_blank");
        alert(`${res.data.files_count} dosya indirildi!`);
      } else {
        alert("İndirme başarısız");
      }
    } catch (e) {
      alert("Hata: " + e.message);
    }
    setDownloading(false);
  };

  // Download YouTube
  const downloadYouTube = async (url, format) => {
    setYtDownloading(true);
    try {
      const res = await axios.post(`${API}/download/youtube`, { url, format });
      if (res.data.success) {
        window.open(`${API}/download/youtube-file/${res.data.filename}`, "_blank");
        alert(`İndirildi: ${res.data.title}`);
      } else {
        alert("İndirme başarısız: " + res.data.message);
      }
    } catch (e) {
      alert("Hata: " + e.message);
    }
    setYtDownloading(false);
  };

  // Copy texts
  const copyTexts = () => {
    const content = texts.filter(t => selectedTexts.has(t.content)).map(t => t.content).join("\n\n---\n\n");
    navigator.clipboard.writeText(content);
    alert("Kopyalandı!");
  };

  // Select all
  const selectAllImages = () => {
    if (selectedImages.size === images.length) {
      setSelectedImages(new Set());
    } else {
      setSelectedImages(new Set(images.map(i => i.url)));
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
      <header className="bg-gray-800 border-b border-gray-700">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center gap-4">
            <div className="bg-gradient-to-br from-green-500 to-blue-600 p-2 rounded-lg">
              <span className="text-2xl">🔍</span>
            </div>
            <div>
              <h1 className="text-xl font-bold">Gelişmiş Web Tarayıcı</h1>
              <p className="text-gray-400 text-sm">Playwright + yt-dlp • Görsel, Video, YouTube İndirici</p>
            </div>
          </div>
        </div>
      </header>

      {/* URL Input */}
      <div className="bg-gray-800 border-b border-gray-700 px-4 py-6">
        <div className="container mx-auto">
          <div className="flex flex-col md:flex-row gap-4 items-end">
            <div className="flex-1">
              <label className="block text-gray-400 text-sm mb-2">Web Sitesi URL</label>
              <input
                type="text"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder="örn: www.example.com"
                className="w-full bg-gray-700 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-green-500 outline-none"
                disabled={crawlStatus.status === "running"}
              />
            </div>
            <div className="w-32">
              <label className="block text-gray-400 text-sm mb-2">Max Sayfa</label>
              <input
                type="number"
                value={maxPages}
                onChange={(e) => setMaxPages(parseInt(e.target.value) || 30)}
                min="1"
                max="200"
                className="w-full bg-gray-700 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-green-500 outline-none"
                disabled={crawlStatus.status === "running"}
              />
            </div>
            {crawlStatus.status === "running" ? (
              <button onClick={stopCrawl} className="bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-lg font-semibold">
                ⏹ Durdur
              </button>
            ) : (
              <button
                onClick={startCrawl}
                disabled={loading}
                className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg font-semibold"
              >
                {loading ? "⏳ Başlatılıyor..." : "🚀 Taramayı Başlat"}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Progress */}
      {["running", "starting", "completed", "error"].includes(crawlStatus.status) && (
        <div className="bg-gray-800 border-b border-gray-700 px-4 py-4">
          <div className="container mx-auto">
            <ProgressBar progress={crawlStatus} status={crawlStatus.status} />
          </div>
        </div>
      )}

      {/* Stats */}
      {summary && (
        <div className="container mx-auto px-4 py-6">
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard title="Sayfa" value={summary.total_urls || 0} icon="📄" color="blue" />
            <StatCard title="Görsel" value={summary.total_images || 0} icon="🖼️" color="green" />
            <StatCard title="Video" value={summary.total_videos || 0} icon="🎬" color="purple" />
            <StatCard title="YouTube" value={summary.total_youtube || 0} icon="▶" color="red" />
            <StatCard title="Metin" value={summary.total_texts || 0} icon="📝" color="yellow" />
            <StatCard title="Sorun" value={summary.issues_count || 0} icon="⚠️" color="pink" />
          </div>
        </div>
      )}

      {/* Tabs */}
      <nav className="bg-gray-800 border-b border-gray-700">
        <div className="container mx-auto px-4">
          <div className="flex gap-1 overflow-x-auto">
            {[
              { id: "images", label: "🖼️ Görseller", count: images.length },
              { id: "youtube", label: "▶ YouTube", count: videos.youtube?.length || 0 },
              { id: "videos", label: "🎬 Videolar", count: videos.videos?.length || 0 },
              { id: "texts", label: "📝 Metinler", count: texts.length },
              { id: "issues", label: "⚠️ Sorunlar", count: issues.length },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`px-4 py-3 font-medium whitespace-nowrap ${
                  activeTab === tab.id ? "text-green-400 border-b-2 border-green-400" : "text-gray-400 hover:text-white"
                }`}
              >
                {tab.label}
                {tab.count > 0 && <span className="ml-2 bg-gray-700 px-2 py-0.5 rounded-full text-xs">{tab.count}</span>}
              </button>
            ))}
          </div>
        </div>
      </nav>

      {/* Content */}
      <main className="container mx-auto px-4 py-6">
        {/* Images */}
        {activeTab === "images" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between flex-wrap gap-4">
              <div className="flex items-center gap-4">
                <button onClick={selectAllImages} className="bg-gray-700 hover:bg-gray-600 text-white px-4 py-2 rounded-lg text-sm">
                  {selectedImages.size === images.length && images.length > 0 ? "Seçimi Kaldır" : "Tümünü Seç"}
                </button>
                <span className="text-gray-400">{selectedImages.size} seçili</span>
              </div>
              <button
                onClick={downloadImages}
                disabled={selectedImages.size === 0 || downloading}
                className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-6 py-2 rounded-lg font-semibold"
              >
                {downloading ? "⏳ İndiriliyor..." : `📥 İndir (${selectedImages.size})`}
              </button>
            </div>
            
            <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
              {images.map((image, i) => (
                <ImageCard
                  key={i}
                  image={image}
                  selected={selectedImages.has(image.url)}
                  onToggle={() => {
                    const newSet = new Set(selectedImages);
                    newSet.has(image.url) ? newSet.delete(image.url) : newSet.add(image.url);
                    setSelectedImages(newSet);
                  }}
                />
              ))}
            </div>
            
            {images.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <p className="text-4xl mb-4">🖼️</p>
                <p>Görsel bulunamadı. Site tarayın.</p>
              </div>
            )}
          </div>
        )}

        {/* YouTube */}
        {activeTab === "youtube" && (
          <div className="space-y-4">
            <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-4 mb-4">
              <p className="text-yellow-400 font-semibold">⚠️ YouTube İndirme</p>
              <p className="text-yellow-200 text-sm mt-1">Kişisel kullanım için. Ticari kullanım ve dağıtım yasaktır.</p>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
              {(videos.youtube || []).map((video, i) => (
                <YouTubeCard key={i} video={video} onDownload={downloadYouTube} downloading={ytDownloading} />
              ))}
            </div>
            
            {(!videos.youtube || videos.youtube.length === 0) && (
              <div className="text-center py-12 text-gray-500">
                <p className="text-4xl mb-4">▶</p>
                <p>YouTube videosu bulunamadı.</p>
              </div>
            )}
          </div>
        )}

        {/* Videos */}
        {activeTab === "videos" && (
          <div className="space-y-4">
            {(videos.videos || []).map((video, i) => (
              <div key={i} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <div className="flex items-center gap-4">
                  <span className="text-3xl">🎬</span>
                  <div className="flex-1">
                    <p className="text-gray-300 truncate">{video.url}</p>
                    <p className="text-gray-500 text-sm">{video.type}</p>
                  </div>
                  <a
                    href={video.url}
                    target="_blank"
                    rel="noreferrer"
                    className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg text-sm"
                  >
                    Aç
                  </a>
                </div>
              </div>
            ))}
            
            {(!videos.videos || videos.videos.length === 0) && (
              <div className="text-center py-12 text-gray-500">
                <p className="text-4xl mb-4">🎬</p>
                <p>Video bulunamadı.</p>
              </div>
            )}
          </div>
        )}

        {/* Texts */}
        {activeTab === "texts" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-gray-400">{selectedTexts.size} seçili</span>
              <button
                onClick={copyTexts}
                disabled={selectedTexts.size === 0}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg"
              >
                📋 Kopyala ({selectedTexts.size})
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {texts.map((text, i) => (
                <TextCard
                  key={i}
                  text={text}
                  selected={selectedTexts.has(text.content)}
                  onToggle={() => {
                    const newSet = new Set(selectedTexts);
                    newSet.has(text.content) ? newSet.delete(text.content) : newSet.add(text.content);
                    setSelectedTexts(newSet);
                  }}
                />
              ))}
            </div>
            
            {texts.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <p className="text-4xl mb-4">📝</p>
                <p>Metin bulunamadı.</p>
              </div>
            )}
          </div>
        )}

        {/* Issues */}
        {activeTab === "issues" && (
          <div className="space-y-4">
            {issues.map((issue, i) => (
              <div key={i} className="bg-gray-800 rounded-lg p-4 border border-gray-700">
                <p className="text-gray-300">{issue.issue_type}</p>
                <p className="text-gray-500 text-sm truncate">{issue.source_url}</p>
                <p className="text-yellow-400 text-sm mt-2">{issue.fix_suggestion}</p>
              </div>
            ))}
            
            {issues.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <p className="text-4xl mb-4">✅</p>
                <p>Sorun yok!</p>
              </div>
            )}
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 py-4 mt-8">
        <div className="container mx-auto px-4 text-center text-gray-500 text-sm">
          <p>Gelişmiş Web Tarayıcı • Playwright + yt-dlp</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
