/** OpenWhip assets (local first, CDN fallback) + volume/mute controls. */
export const WHIP_CDN = "https://raw.githubusercontent.com/GitFrog1111/OpenWhip/main";
export const WHIP_SOUND_FILES = ["A.mp3", "B.mp3", "C.mp3", "D.mp3", "E.mp3"] as const;

export const WHIP_CURSOR =
  'url("/whip/divider.png") 8 8, url("' +
  WHIP_CDN +
  '/assets/divider.png") 8 8, crosshair';

export function getWhipVolume(): number {
  try {
    if (localStorage.getItem("dana-whip-muted") === "1") return 0;
    const raw = localStorage.getItem("dana-whip-volume");
    if (raw !== null) {
      const v = Number(raw);
      if (Number.isFinite(v)) return Math.max(0, Math.min(1, v));
    }
  } catch {
    /* ignore */
  }
  return 0.85;
}

export function setWhipVolume(vol: number): void {
  try {
    const clamped = Math.max(0, Math.min(1, vol));
    localStorage.setItem("dana-whip-volume", String(clamped));
    if (clamped > 0) localStorage.setItem("dana-whip-muted", "0");
  } catch {
    /* ignore */
  }
}

export function isWhipMuted(): boolean {
  try {
    return localStorage.getItem("dana-whip-muted") === "1" || getWhipVolume() === 0;
  } catch {
    return false;
  }
}

export function setWhipMuted(muted: boolean): void {
  try {
    localStorage.setItem("dana-whip-muted", muted ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function playOpenWhipCrack(fallback?: () => void): void {
  try {
    const vol = getWhipVolume();
    if (vol <= 0) return;
    const name = WHIP_SOUND_FILES[Math.floor(Math.random() * WHIP_SOUND_FILES.length)];
    const local = "/whip/sounds/" + name;
    const remote = WHIP_CDN + "/sounds/" + name;
    const audio = new Audio(local);
    audio.volume = vol;
    const playRemote = () => {
      try {
        const a = new Audio(remote);
        a.volume = vol;
        void a.play().catch(() => fallback?.());
      } catch {
        fallback?.();
      }
    };
    audio.addEventListener("error", playRemote);
    void audio.play().catch(playRemote);
  } catch {
    fallback?.();
  }
}
