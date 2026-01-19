import { useState, useEffect, useCallback, useRef } from "react";
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

// Download Progress Bar Component
const DownloadProgressBar = ({ downloadId, progress, onComplete }) => {
  const getStatusColor = () => {
    switch (progress?.status) {
      case 'completed': return 'bg-green-500';
      case 'failed': return 'bg-red-500';
      case 'queued': return 'bg-yellow-500';
      case 'processing': return 'bg-blue-400';
      default: return 'bg-blue-500';
    }
  };

  const getStatusText = () => {
    switch (progress?.status) {
      case 'queued': return `Sırada bekliyor (#${progress.queue_position || '?'})`;
      case 'starting': return 'Başlatılıyor...';
      case 'downloading': return `İndiriliyor... ${progress.speed || ''}`;
      case 'processing': return 'İşleniyor...';
      case 'completed': return 'Tamamlandı!';
      case 'failed': return 'Başarısız';
      default: return 'Hazırlanıyor...';
    }
  };

  useEffect(() => {
    if (progress?.status === 'completed' && progress?.result?.download_url) {
      // Otomatik indirme başlat
      window.open(`${API}${progress.result.download_url.replace('/api', '')}`, "_blank");
      if (onComplete) onComplete(downloadId, progress.result);
    }
  }, [progress?.status, progress?.result, downloadId, onComplete]);

  return (
    <div className="bg-gray-700 rounded-lg p-3 mb-2">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm text-gray-300 truncate flex-1 mr-2">
          {progress?.result?.title || downloadId}
        </span>
        <span className="text-xs text-gray-400 whitespace-nowrap">
          {progress?.downloaded && progress?.total ? `${progress.downloaded} / ${progress.total}` : ''}
          {progress?.eta ? ` • ${progress.eta}` : ''}
        </span>
      </div>
      <div className="w-full bg-gray-600 rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full transition-all duration-300 ${getStatusColor()}`}
          style={{ width: `${Math.min(progress?.percent || 0, 100)}%` }}
        />
      </div>
      <div className="flex justify-between mt-1">
        <span className="text-xs text-gray-400">{getStatusText()}</span>
        <span className="text-xs text-gray-400">{Math.round(progress?.percent || 0)}%</span>
      </div>
    </div>
  );
};

// Download Queue Status Component
const DownloadQueueStatus = ({ queueStatus, onClear, onResume, onDeleteIncomplete }) => {
  const hasActiveDownloads = queueStatus && Object.keys(queueStatus.progress || {}).length > 0;
  const hasIncomplete = queueStatus && Object.keys(queueStatus.incomplete || {}).length > 0;
  
  if (!hasActiveDownloads && !hasIncomplete) {
    return null;
  }

  return (
    <div className="bg-gray-800 rounded-xl p-4 border border-gray-700 mb-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
          <span>📊</span> İndirme Durumu
          <span className="bg-blue-600 text-xs px-2 py-0.5 rounded-full">
            {queueStatus.active_count}/{queueStatus.max_concurrent} aktif
          </span>
          {queueStatus.queue_count > 0 && (
            <span className="bg-yellow-600 text-xs px-2 py-0.5 rounded-full">
              {queueStatus.queue_count} sırada
            </span>
          )}
        </h4>
        {Object.keys(queueStatus.progress || {}).length > 0 && (
          <button
            onClick={onClear}
            className="text-xs text-gray-400 hover:text-white"
          >
            Temizle
          </button>
        )}
      </div>
      
      {/* Aktif İndirmeler */}
      {hasActiveDownloads && (
        <div className="space-y-2 max-h-48 overflow-y-auto mb-4">
          {Object.entries(queueStatus.progress || {}).map(([id, prog]) => (
            <div key={id} className="bg-gray-700 rounded-lg p-3">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-gray-300 truncate flex-1 mr-2">
                  {prog?.title || prog?.url || id}
                </span>
                <span className="text-xs text-gray-400 whitespace-nowrap">
                  {prog?.downloaded && prog?.total ? `${prog.downloaded} / ${prog.total}` : ''}
                  {prog?.eta ? ` • ${prog.eta}` : ''}
                </span>
              </div>
              <div className="w-full bg-gray-600 rounded-full h-2.5">
                <div
                  className={`h-2.5 rounded-full transition-all duration-300 ${
                    prog?.status === 'completed' ? 'bg-green-500' :
                    prog?.status === 'failed' ? 'bg-red-500' :
                    prog?.status === 'queued' ? 'bg-yellow-500' :
                    prog?.status === 'processing' ? 'bg-purple-500' : 'bg-blue-500'
                  }`}
                  style={{ width: `${Math.min(prog?.percent || 0, 100)}%` }}
                />
              </div>
              <div className="flex justify-between mt-1">
                <span className="text-xs text-gray-400">
                  {prog?.status === 'queued' ? `Sırada (#${prog?.queue_position || '?'})` :
                   prog?.status === 'starting' ? 'Başlatılıyor...' :
                   prog?.status === 'downloading' ? `İndiriliyor... ${prog?.speed || ''}` :
                   prog?.status === 'processing' ? 'İşleniyor...' :
                   prog?.status === 'completed' ? 'Tamamlandı!' :
                   prog?.status === 'failed' ? 'Başarısız' : 'Hazırlanıyor...'}
                </span>
                <span className="text-xs text-gray-400">{Math.round(prog?.percent || 0)}%</span>
              </div>
            </div>
          ))}
        </div>
      )}
      
      {/* Yarım Kalan İndirmeler */}
      {hasIncomplete && (
        <div className="border-t border-gray-600 pt-3">
          <div className="flex items-center justify-between mb-2">
            <h5 className="text-xs font-semibold text-orange-400 flex items-center gap-1">
              <span>⏸️</span> Yarım Kalan İndirmeler
            </h5>
          </div>
          <div className="space-y-2 max-h-32 overflow-y-auto">
            {Object.entries(queueStatus.incomplete || {}).map(([id, item]) => (
              <div key={id} className="bg-gray-700/50 rounded-lg p-2 flex items-center gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-xs text-gray-300 truncate">{item.title || item.url}</p>
                  <p className="text-xs text-gray-500">%{item.percent || 0} tamamlandı</p>
                </div>
                <button
                  onClick={() => onResume(id)}
                  className="bg-green-600 hover:bg-green-700 text-white px-2 py-1 rounded text-xs font-semibold flex items-center gap-1"
                >
                  ▶️ Devam
                </button>
                <button
                  onClick={() => onDeleteIncomplete(id)}
                  className="bg-red-600/50 hover:bg-red-600 text-white px-2 py-1 rounded text-xs"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
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

// YouTube Card with Progress
const YouTubeCard = ({ video, onDownload, downloadProgress, isDownloading }) => {
  const hasProgress = downloadProgress && downloadProgress.status !== 'completed';
  
  return (
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
        
        {hasProgress ? (
          <div className="space-y-2">
            <div className="w-full bg-gray-600 rounded-full h-2">
              <div
                className={`h-2 rounded-full transition-all duration-300 ${
                  downloadProgress.status === 'queued' ? 'bg-yellow-500' : 'bg-blue-500'
                }`}
                style={{ width: `${downloadProgress.percent || 0}%` }}
              />
            </div>
            <p className="text-xs text-gray-400 text-center">
              {downloadProgress.status === 'queued' 
                ? `Sırada (#${downloadProgress.queue_position})` 
                : `${Math.round(downloadProgress.percent || 0)}% ${downloadProgress.speed || ''}`}
            </p>
          </div>
        ) : (
          <div className="flex gap-2">
            <button
              onClick={() => onDownload(video.url, "video")}
              disabled={isDownloading}
              className="flex-1 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 text-white px-2 py-1.5 rounded text-xs font-semibold"
            >
              {isDownloading ? "⏳" : "📹"} Video
            </button>
            <button
              onClick={() => onDownload(video.url, "audio")}
              disabled={isDownloading}
              className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 text-white px-2 py-1.5 rounded text-xs font-semibold"
            >
              {isDownloading ? "⏳" : "🎵"} MP3
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

// Direct Video Downloader Component with Progress
const DirectVideoDownloader = ({ queueStatus, onQueueUpdate }) => {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [videoInfo, setVideoInfo] = useState(null);
  const [activeDownloads, setActiveDownloads] = useState({});
  const pollIntervalRef = useRef(null);

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

  // Polling for download progress
  useEffect(() => {
    const pollProgress = async () => {
      if (Object.keys(activeDownloads).length === 0) return;
      
      try {
        const res = await axios.get(`${API}/download/queue-status`);
        if (res.data && res.data.progress) {
          // Update active downloads with new progress
          const newActiveDownloads = { ...activeDownloads };
          let hasChanges = false;
          
          for (const [downloadId, info] of Object.entries(activeDownloads)) {
            const progress = res.data.progress[downloadId];
            if (progress) {
              newActiveDownloads[downloadId] = { ...info, progress };
              hasChanges = true;
              
              // Check if completed
              if (progress.status === 'completed' && progress.result?.download_url) {
                window.open(`${API}${progress.result.download_url.replace('/api', '')}`, "_blank");
                delete newActiveDownloads[downloadId];
              } else if (progress.status === 'failed') {
                alert(`İndirme başarısız: ${progress.result?.message || 'Bilinmeyen hata'}`);
                delete newActiveDownloads[downloadId];
              }
            }
          }
          
          if (hasChanges) {
            setActiveDownloads(newActiveDownloads);
          }
          
          if (onQueueUpdate) {
            onQueueUpdate(res.data);
          }
        }
      } catch (e) {
        console.error('Progress poll error:', e);
      }
    };

    if (Object.keys(activeDownloads).length > 0) {
      pollIntervalRef.current = setInterval(pollProgress, 1000);
      return () => clearInterval(pollIntervalRef.current);
    }
  }, [activeDownloads, onQueueUpdate]);

  const downloadVideo = async (format) => {
    try {
      const res = await axios.post(`${API}/download/video`, { url, format });
      if (res.data.success) {
        // Add to active downloads
        setActiveDownloads(prev => ({
          ...prev,
          [res.data.download_id]: {
            url,
            format,
            title: videoInfo?.title || url,
            status: res.data.status,
            queue_position: res.data.queue_position,
            progress: { percent: 0, status: res.data.status }
          }
        }));
        
        if (res.data.status === 'queued') {
          // Show queue message
        }
      } else {
        alert("İndirme başarısız: " + res.data.message);
      }
    } catch (e) {
      alert("Hata: " + e.message);
    }
  };

  const hasActiveDownloads = Object.keys(activeDownloads).length > 0;

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-bold flex items-center gap-2">
          <span>🎬</span> Video İndir
          <span className="text-xs text-gray-500 font-normal">(YouTube, VK, TikTok, Twitter, Instagram...)</span>
        </h3>
        {queueStatus && (
          <div className="flex items-center gap-2 text-xs">
            <span className="bg-blue-600 px-2 py-1 rounded-full">
              {queueStatus.active_count}/{queueStatus.max_concurrent} aktif
            </span>
            {queueStatus.queue_count > 0 && (
              <span className="bg-yellow-600 px-2 py-1 rounded-full">
                {queueStatus.queue_count} sırada
              </span>
            )}
          </div>
        )}
      </div>
      
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Video URL yapıştır (örn: youtube.com/watch?v=..., vk.com/video...)"
          className="flex-1 bg-gray-700 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 outline-none"
        />
        <button
          onClick={checkVideo}
          disabled={loading || !url}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg font-semibold"
        >
          {loading ? "⏳" : "🔍"} Kontrol
        </button>
      </div>

      {/* Active Downloads Progress */}
      {hasActiveDownloads && (
        <div className="mb-4 space-y-2">
          <p className="text-sm text-gray-400 mb-2">📥 Aktif İndirmeler:</p>
          {Object.entries(activeDownloads).map(([id, download]) => (
            <div key={id} className="bg-gray-700 rounded-lg p-3">
              <div className="flex justify-between items-center mb-2">
                <span className="text-sm text-gray-300 truncate flex-1 mr-2">
                  {download.title}
                </span>
                <span className="text-xs text-gray-400">
                  {download.progress?.status === 'queued' 
                    ? `Sırada (#${download.progress?.queue_position || download.queue_position})` 
                    : download.progress?.speed || ''}
                </span>
              </div>
              <div className="w-full bg-gray-600 rounded-full h-2.5">
                <div
                  className={`h-2.5 rounded-full transition-all duration-300 ${
                    download.progress?.status === 'queued' ? 'bg-yellow-500' :
                    download.progress?.status === 'completed' ? 'bg-green-500' :
                    download.progress?.status === 'failed' ? 'bg-red-500' : 'bg-blue-500'
                  }`}
                  style={{ width: `${download.progress?.percent || 0}%` }}
                />
              </div>
              <div className="flex justify-between mt-1">
                <span className="text-xs text-gray-400">
                  {download.progress?.status === 'downloading' ? 'İndiriliyor...' :
                   download.progress?.status === 'processing' ? 'İşleniyor...' :
                   download.progress?.status === 'queued' ? 'Beklemede' :
                   download.progress?.status === 'starting' ? 'Başlatılıyor...' : ''}
                </span>
                <span className="text-xs text-gray-400">{Math.round(download.progress?.percent || 0)}%</span>
              </div>
            </div>
          ))}
        </div>
      )}

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
              disabled={queueStatus && queueStatus.active_count >= queueStatus.max_concurrent && queueStatus.queue_count >= 10}
              className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold"
            >
              📹 Video İndir
            </button>
            <button
              onClick={() => downloadVideo("audio")}
              disabled={queueStatus && queueStatus.active_count >= queueStatus.max_concurrent && queueStatus.queue_count >= 10}
              className="flex-1 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold"
            >
              🎵 MP3 İndir
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

// Direct Image Downloader Component
const DirectImageDownloader = () => {
  const [url, setUrl] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [preview, setPreview] = useState(null);

  const downloadImage = async () => {
    if (!url) {
      alert("Resim URL'si girin!");
      return;
    }
    setDownloading(true);
    try {
      const res = await axios.post(`${API}/download/direct-image?url=${encodeURIComponent(url)}`);
      if (res.data.success) {
        window.open(`${API}/download/file-direct/${res.data.filename}`, "_blank");
        alert(`İndirildi: ${res.data.filename} (${res.data.size_kb.toFixed(1)} KB)`);
        setPreview(null);
        setUrl("");
      } else {
        alert("İndirme başarısız: " + res.data.message);
      }
    } catch (e) {
      alert("Hata: " + e.message);
    }
    setDownloading(false);
  };

  const previewImage = () => {
    if (url) setPreview(url);
  };

  return (
    <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
      <h3 className="text-lg font-bold mb-4 flex items-center gap-2">
        <span>🖼️</span> Resim İndir
        <span className="text-xs text-gray-500 font-normal">(Herhangi bir resim URL'si)</span>
      </h3>
      
      <div className="flex gap-3 mb-4">
        <input
          type="text"
          value={url}
          onChange={(e) => { setUrl(e.target.value); setPreview(null); }}
          placeholder="Resim URL yapıştır (örn: site.com/image.jpg)"
          className="flex-1 bg-gray-700 text-white rounded-lg px-4 py-3 focus:ring-2 focus:ring-green-500 outline-none"
        />
        <button
          onClick={previewImage}
          disabled={!url}
          className="bg-gray-600 hover:bg-gray-500 disabled:bg-gray-700 text-white px-4 py-3 rounded-lg font-semibold"
        >
          👁️ Önizle
        </button>
        <button
          onClick={downloadImage}
          disabled={downloading || !url}
          className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-6 py-3 rounded-lg font-semibold"
        >
          {downloading ? "⏳ İndiriliyor..." : "📥 İndir"}
        </button>
      </div>

      {preview && (
        <div className="mt-4 p-4 bg-gray-700 rounded-lg">
          <p className="text-gray-400 text-sm mb-2">Önizleme:</p>
          <img 
            src={preview} 
            alt="Preview" 
            className="max-w-full max-h-64 rounded-lg mx-auto"
            onError={(e) => { e.target.src = "https://via.placeholder.com/300x200?text=Yüklenemedi"; }}
          />
        </div>
      )}
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
  const [activeTab, setActiveTab] = useState("direct");
  const [crawlStatus, setCrawlStatus] = useState({ status: "idle", crawled: 0, discovered: 0, images: 0, videos: 0, message: "" });
  const [summary, setSummary] = useState(null);
  const [images, setImages] = useState([]);
  const [videos, setVideos] = useState({ videos: [], youtube: [] });
  const [texts, setTexts] = useState([]);
  const [issues, setIssues] = useState([]);
  const [selectedImages, setSelectedImages] = useState(new Set());
  const [selectedTexts, setSelectedTexts] = useState(new Set());
  const [selectedVideos, setSelectedVideos] = useState(new Set());
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [ytDownloading, setYtDownloading] = useState(false);
  const [downloadQueue, setDownloadQueue] = useState(null);
  const [videoDownloadProgress, setVideoDownloadProgress] = useState({});

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
    setSelectedVideos(new Set());
    
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

  // Download YouTube with queue system
  const downloadYouTube = async (url, format) => {
    try {
      const res = await axios.post(`${API}/download/youtube`, { url, format });
      if (res.data.success) {
        // Track this download
        setVideoDownloadProgress(prev => ({
          ...prev,
          [res.data.download_id]: {
            status: res.data.status,
            queue_position: res.data.queue_position,
            percent: 0,
            url
          }
        }));
      } else {
        alert("İndirme başarısız: " + res.data.message);
      }
    } catch (e) {
      alert("Hata: " + e.message);
    }
  };

  // Fetch download queue status
  const fetchDownloadQueue = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/download/queue-status`);
      setDownloadQueue(res.data);
      
      // Update video download progress
      if (res.data.progress) {
        setVideoDownloadProgress(prev => {
          const updated = { ...prev };
          for (const [id, prog] of Object.entries(res.data.progress)) {
            if (updated[id]) {
              updated[id] = { ...updated[id], ...prog };
              
              // Auto-download completed files
              if (prog.status === 'completed' && prog.result?.download_url) {
                window.open(`${API}${prog.result.download_url.replace('/api', '')}`, "_blank");
                delete updated[id];
              } else if (prog.status === 'failed') {
                delete updated[id];
              }
            }
          }
          return updated;
        });
      }
    } catch (e) { console.error(e); }
  }, []);

  // Clear completed downloads
  const clearCompletedDownloads = async () => {
    try {
      await axios.post(`${API}/download/clear-completed`);
      setDownloadQueue(prev => prev ? { ...prev, progress: {} } : null);
    } catch (e) { console.error(e); }
  };

  // Resume incomplete download
  const resumeIncompleteDownload = async (downloadId) => {
    try {
      const res = await axios.post(`${API}/download/resume/${downloadId}`);
      if (res.data.success) {
        fetchDownloadQueue(); // Refresh queue status
      } else {
        alert("Devam ettirilemedi: " + res.data.message);
      }
    } catch (e) {
      alert("Hata: " + e.message);
    }
  };

  // Delete incomplete download
  const deleteIncompleteDownload = async (downloadId) => {
    try {
      await axios.delete(`${API}/download/incomplete/${downloadId}`);
      fetchDownloadQueue(); // Refresh queue status
    } catch (e) {
      console.error(e);
    }
  };

  // Download selected videos (bulk)
  const downloadSelectedVideos = async () => {
    if (selectedVideos.size === 0) {
      alert("Video seçin!");
      return;
    }
    
    // Her video için indirme başlat
    for (const videoUrl of selectedVideos) {
      try {
        const res = await axios.post(`${API}/download/video`, { url: videoUrl, format: 'video' });
        if (res.data.success) {
          setVideoDownloadProgress(prev => ({
            ...prev,
            [res.data.download_id]: {
              status: res.data.status,
              queue_position: res.data.queue_position,
              percent: 0,
              url: videoUrl
            }
          }));
        }
      } catch (e) {
        console.error('Video download error:', e);
      }
    }
    
    setSelectedVideos(new Set());
    alert(`${selectedVideos.size} video indirme sırasına eklendi!`);
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

  // Download queue polling
  useEffect(() => {
    fetchDownloadQueue();
    const interval = setInterval(fetchDownloadQueue, 1500);
    return () => clearInterval(interval);
  }, [fetchDownloadQueue]);

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
              { id: "direct", label: "📥 Direkt İndir", count: null },
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
        {/* Direct Download Tab */}
        {activeTab === "direct" && (
          <div className="space-y-6">
            <div className="text-center mb-6">
              <h2 className="text-2xl font-bold text-white mb-2">🚀 Direkt İndir</h2>
              <p className="text-gray-400">Site taramadan direkt link yapıştırıp indir • Maks 5 eşzamanlı indirme</p>
            </div>
            
            {/* Download Queue Status */}
            <DownloadQueueStatus 
              queueStatus={downloadQueue} 
              onClear={clearCompletedDownloads}
              onResume={resumeIncompleteDownload}
              onDeleteIncomplete={deleteIncompleteDownload}
            />
            
            <DirectVideoDownloader queueStatus={downloadQueue} onQueueUpdate={setDownloadQueue} />
            <DirectImageDownloader />
            
            <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
              <h3 className="text-lg font-bold mb-4">📋 Desteklenen Video Siteleri</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-sm">
                {["YouTube", "VK.com", "TikTok", "Twitter/X", "Instagram", "Facebook", "Dailymotion", "Vimeo", "Twitch", "Reddit", "Bilibili", "SoundCloud"].map(site => (
                  <div key={site} className="bg-gray-700 rounded px-3 py-2 text-center text-gray-300">
                    {site}
                  </div>
                ))}
              </div>
              <p className="text-gray-500 text-xs mt-3 text-center">ve 1000+ site daha...</p>
            </div>
          </div>
        )}

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
            {/* Download Queue Status */}
            <DownloadQueueStatus 
              queueStatus={downloadQueue} 
              onClear={clearCompletedDownloads}
              onResume={resumeIncompleteDownload}
              onDeleteIncomplete={deleteIncompleteDownload}
            />
            
            {/* Direct Video Downloader */}
            <DirectVideoDownloader queueStatus={downloadQueue} onQueueUpdate={setDownloadQueue} />
            
            <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-4 mb-4">
              <p className="text-yellow-400 font-semibold">⚠️ Video İndirme</p>
              <p className="text-yellow-200 text-sm mt-1">Kişisel kullanım için. Ticari kullanım ve dağıtım yasaktır. Maks 5 eşzamanlı indirme.</p>
            </div>
            
            {(videos.youtube && videos.youtube.length > 0) && (
              <>
                <h3 className="text-lg font-semibold text-gray-300">Sitede Bulunan YouTube Videoları</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-4">
                  {videos.youtube.map((video, i) => (
                    <YouTubeCard 
                      key={i} 
                      video={video} 
                      onDownload={downloadYouTube} 
                      downloadProgress={videoDownloadProgress[video.url]}
                      isDownloading={Object.keys(videoDownloadProgress).length >= 5}
                    />
                  ))}
                </div>
              </>
            )}
            
            {(!videos.youtube || videos.youtube.length === 0) && (
              <div className="text-center py-8 text-gray-500">
                <p className="text-2xl mb-2">👆</p>
                <p>Yukarıdan herhangi bir video URL'si yapıştırarak indirin!</p>
              </div>
            )}
          </div>
        )}

        {/* Videos */}
        {activeTab === "videos" && (
          <div className="space-y-4">
            {/* Download Queue Status */}
            <DownloadQueueStatus 
              queueStatus={downloadQueue} 
              onClear={clearCompletedDownloads}
              onResume={resumeIncompleteDownload}
              onDeleteIncomplete={deleteIncompleteDownload}
            />
            
            {/* Selection toolbar */}
            {(videos.videos || []).length > 0 && (
              <div className="flex items-center justify-between bg-gray-800 rounded-lg p-4 border border-gray-700">
                <div className="flex items-center gap-4">
                  <span className="text-gray-400">{selectedVideos.size} video seçili</span>
                  <button
                    onClick={() => {
                      if (selectedVideos.size === (videos.videos || []).length) {
                        setSelectedVideos(new Set());
                      } else {
                        setSelectedVideos(new Set((videos.videos || []).map(v => v.url)));
                      }
                    }}
                    className="text-sm text-blue-400 hover:text-blue-300"
                  >
                    {selectedVideos.size === (videos.videos || []).length ? "Tümünü Kaldır" : "Tümünü Seç"}
                  </button>
                </div>
                <button
                  onClick={downloadSelectedVideos}
                  disabled={selectedVideos.size === 0}
                  className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white px-4 py-2 rounded-lg font-semibold flex items-center gap-2"
                >
                  📥 Seçilenleri İndir ({selectedVideos.size})
                </button>
              </div>
            )}
            
            {/* Video grid - thumbnail'lı kartlar */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {(videos.videos || []).map((video, i) => (
                <div 
                  key={i} 
                  className={`bg-gray-800 rounded-lg overflow-hidden border-2 cursor-pointer transition-all ${
                    selectedVideos.has(video.url) ? "border-green-500 ring-2 ring-green-500" : "border-gray-700 hover:border-gray-500"
                  }`}
                  onClick={() => {
                    const newSet = new Set(selectedVideos);
                    if (newSet.has(video.url)) {
                      newSet.delete(video.url);
                    } else {
                      newSet.add(video.url);
                    }
                    setSelectedVideos(newSet);
                  }}
                >
                  {/* Thumbnail veya placeholder */}
                  <div className="relative h-40 bg-gray-900">
                    {video.thumbnail ? (
                      <img
                        src={video.thumbnail}
                        alt={video.title || "Video"}
                        className="w-full h-full object-cover"
                        onError={(e) => { e.target.style.display = 'none'; }}
                      />
                    ) : (
                      <div className="flex items-center justify-center h-full">
                        <span className="text-6xl opacity-50">🎬</span>
                      </div>
                    )}
                    {/* Seçim işareti */}
                    {selectedVideos.has(video.url) && (
                      <div className="absolute top-2 right-2 bg-green-500 rounded-full p-1">
                        <span className="text-white text-lg">✓</span>
                      </div>
                    )}
                    {/* Video tipi badge */}
                    <div className="absolute bottom-2 left-2 bg-black/70 rounded px-2 py-1 text-xs text-white">
                      {video.type === 'vk' ? '📹 VK' : video.type === 'vimeo' ? '📹 Vimeo' : '📹 Video'}
                    </div>
                  </div>
                  
                  {/* Video bilgileri */}
                  <div className="p-3">
                    <p className="text-sm text-gray-300 truncate mb-2" title={video.url}>
                      {video.title || video.url}
                    </p>
                    <div className="flex gap-2">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          downloadYouTube(video.url, 'video');
                        }}
                        className="flex-1 bg-green-600 hover:bg-green-700 text-white px-3 py-2 rounded-lg text-sm font-medium"
                      >
                        📥 Video
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          downloadYouTube(video.url, 'audio');
                        }}
                        className="flex-1 bg-purple-600 hover:bg-purple-700 text-white px-3 py-2 rounded-lg text-sm font-medium"
                      >
                        🎵 MP3
                      </button>
                      <a
                        href={video.url}
                        target="_blank"
                        rel="noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-2 rounded-lg text-sm"
                      >
                        🔗
                      </a>
                    </div>
                  </div>
                </div>
              ))}
            </div>
            
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
