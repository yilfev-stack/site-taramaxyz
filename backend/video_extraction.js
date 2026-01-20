() => {
    const vids = [];
    const seen = new Set();
    const currentUrl = window.location.href;
    const isVkSite = currentUrl.includes('vk.com') || currentUrl.includes('vkvideo.ru');
    const getBackgroundImage = (el) => {
        if (!el) return '';
        const style = getComputedStyle(el).backgroundImage;
        if (!style || style === 'none') {
            return '';
        }
        const match = style.match(/url\(["']?([^"')]+)["']?\)/);
        return match ? match[1] : '';
    };
    const isVisible = (el) => {
        if (!el) return false;
        if (el.hidden) return false;
        const style = window.getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') {
            return false;
        }
        return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    };
    const isInViewport = (el) => {
        if (!el) return false;
        const rect = el.getBoundingClientRect();
        return rect.bottom > 0 && rect.right > 0 &&
            rect.top < (window.innerHeight || document.documentElement.clientHeight) &&
            rect.left < (window.innerWidth || document.documentElement.clientWidth);
    };
    const shouldIncludeElement = (el) => isVisible(el) && isInViewport(el);

    // VK video sayfalarında - video kartlarından URL'leri çıkar
    if (isVkSite) {
        // VK video kartları - farklı seçiciler dene
        const vkSelectors = [
            'a[href*="/video-"]',
            'a[href*="/video@"]',
            'a[href*="video"][href*="_"]',
            '[data-video-id]',
            '.VideoCard a',
            '.video_item a',
            '.VideoThumb a'
        ];

        vkSelectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                if (!shouldIncludeElement(el)) {
                    return;
                }
                let href = el.href || el.getAttribute('href');
                const videoId = el.dataset?.videoId;
                const rawId = el.dataset?.videoRawId;
                const thumbData = el.dataset?.thumb || el.dataset?.preview || el.dataset?.poster;

                // data-video-id varsa URL oluştur
                if (videoId && !href) {
                    href = 'https://vk.com/video' + videoId;
                }
                if (rawId && !href) {
                    href = 'https://vk.com/video' + rawId;
                }

                if (href && !seen.has(href)) {
                    // VK video URL formatını kontrol et
                    const vkMatch = href.match(/video(-?\d+_\d+)/);
                    if (vkMatch) {
                        const cleanUrl = 'https://vk.com/video' + vkMatch[1];
                        if (!seen.has(cleanUrl)) {
                            seen.add(cleanUrl);
                            // Thumbnail bulmaya çalış
                            let thumb = '';
                            const img = el.querySelector('img') || el.closest('.VideoCard')?.querySelector('img');
                            if (img) {
                                thumb = img.src || img.dataset.src || img.dataset.lazy || img.dataset.lazySrc || '';
                            }
                            if (!thumb && thumbData) {
                                thumb = thumbData;
                            }
                            if (!thumb) {
                                thumb = getBackgroundImage(el) || getBackgroundImage(el.closest('.VideoCard') || el);
                            }
                            vids.push({ url: cleanUrl, type: 'vk', thumbnail: thumb });
                        }
                    }
                }
            });
        });
    }

    // CDN video URL'lerini ATLA - bunlar süreli ve çalışmaz
    // Sadece direkt indirilebilir video dosyalarını al (.mp4 dosyaları)
    document.querySelectorAll('video').forEach(v => {
        if (!shouldIncludeElement(v)) {
            return;
        }
        let src = v.src || v.currentSrc;
        // CDN URL'lerini atla
        if (src && !src.startsWith('blob:') && !src.includes('okcdn') && !src.includes('vkuservideo')) {
            // Sadece temiz .mp4/.webm URL'lerini al
            if (src.match(/\.(mp4|webm|mov)(\?|$)/i) && !seen.has(src)) {
                seen.add(src);
                vids.push({ url: src, type: 'video' });
            }
        }
    });

    // YouTube iframes
    document.querySelectorAll('iframe').forEach(iframe => {
        if (!shouldIncludeElement(iframe)) {
            return;
        }
        const src = iframe.src || iframe.dataset.src;
        if (src && !seen.has(src)) {
            if (src.includes('youtube') || src.includes('youtu.be')) {
                seen.add(src);
                vids.push({ url: src, type: 'youtube' });
            } else if (src.includes('vimeo')) {
                seen.add(src);
                vids.push({ url: src, type: 'vimeo' });
            } else if (src.includes('vk.com') || src.includes('vkvideo')) {
                seen.add(src);
                vids.push({ url: src, type: 'vk' });
            } else if (src.includes('dailymotion')) {
                seen.add(src);
                vids.push({ url: src, type: 'dailymotion' });
            }
        }
    });

    // YouTube links
    document.querySelectorAll('a[href*="youtube"], a[href*="youtu.be"]').forEach(a => {
        if (!shouldIncludeElement(a)) {
            return;
        }
        if (!seen.has(a.href)) {
            seen.add(a.href);
            vids.push({ url: a.href, type: 'youtube' });
        }
    });

    // VK video links
    document.querySelectorAll('a[href*="vk.com/video"], a[href*="vkvideo"], a[href*="vkvideo.ru/video"], a[href*="vkvideo.ru/clip"]').forEach(a => {
        if (!shouldIncludeElement(a)) {
            return;
        }
        if (!seen.has(a.href)) {
            seen.add(a.href);
            vids.push({ url: a.href, type: 'vk' });
        }
    });

    // Genel video linkleri (.mp4, .webm, .avi, .mov)
    document.querySelectorAll('a[href$=".mp4"], a[href$=".webm"], a[href$=".avi"], a[href$=".mov"], a[href$=".m3u8"]').forEach(a => {
        if (!shouldIncludeElement(a)) {
            return;
        }
        if (!seen.has(a.href)) {
            seen.add(a.href);
            vids.push({ url: a.href, type: 'video' });
        }
    });

    // data-video attributes
    document.querySelectorAll('[data-video], [data-video-url], [data-video-src]').forEach(el => {
        if (!shouldIncludeElement(el)) {
            return;
        }
        const src = el.dataset.video || el.dataset.videoUrl || el.dataset.videoSrc;
        if (src && !src.startsWith('blob:') && !seen.has(src)) {
            seen.add(src);
            vids.push({ url: src, type: 'video' });
        }
    });

    return vids;
}
