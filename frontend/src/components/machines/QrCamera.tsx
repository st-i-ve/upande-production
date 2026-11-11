import { useEffect, useRef, useState } from "react";

interface DetectedCode {
  rawValue: string;
}
interface BarcodeDetectorLike {
  detect: (source: CanvasImageSource) => Promise<DetectedCode[]>;
}
type BarcodeDetectorCtor = new (opts?: { formats?: string[] }) => BarcodeDetectorLike;

/** The browser's own QR reader (Chrome / Edge on Android, Safari 17+), or null. */
export function barcodeDetector(): BarcodeDetectorCtor | null {
  const Ctor = (globalThis as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector;
  return typeof Ctor === "function" ? Ctor : null;
}

/**
 * The phone's back camera, read for one QR code. Calls `onCode` once with what it decoded and
 * stops the camera. The camera runs only while this is mounted; it never asks for location (the
 * scan screen reads the one GPS fix after `onCode`).
 */
export function QrCamera({ onCode, onUnavailable }: { onCode: (text: string) => void; onUnavailable: (reason: string) => void }) {
  const video = useRef<HTMLVideoElement | null>(null);
  const [status, setStatus] = useState("Starting the camera…");
  const done = useRef(false);

  useEffect(() => {
    const Ctor = barcodeDetector();
    if (!Ctor) {
      onUnavailable("This browser cannot read QR codes. Open the label with the phone's camera app, or type the code printed under it.");
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      onUnavailable("This browser has no camera access here. Type the code printed under the QR code.");
      return;
    }
    let stream: MediaStream | null = null;
    let timer = 0;
    let live = true;
    const detector = new Ctor({ formats: ["qr_code"] });
    const stop = () => {
      live = false;
      window.clearTimeout(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
    const tick = async () => {
      if (!live || !video.current) return;
      try {
        if (video.current.readyState >= 2) {
          const found = await detector.detect(video.current);
          const hit = found.find((f) => f.rawValue);
          if (hit && !done.current) {
            done.current = true;
            stop();
            onCode(hit.rawValue);
            return;
          }
        }
      } catch {
        /* a frame that could not be read: try the next */
      }
      timer = window.setTimeout(tick, 250);
    };
    navigator.mediaDevices
      .getUserMedia({ video: { facingMode: "environment" }, audio: false })
      .then((s) => {
        if (!live) {
          s.getTracks().forEach((t) => t.stop());
          return;
        }
        stream = s;
        if (video.current) {
          video.current.srcObject = s;
          void video.current.play();
        }
        setStatus("Point the camera at the machine's QR label.");
        void tick();
      })
      .catch(() => onUnavailable("The camera was not allowed. Type the code printed under the QR code instead."));
    return stop;
  }, [onCode, onUnavailable]);

  return (
    <div className="flex flex-col gap-2">
      <div className="relative aspect-square w-full max-w-sm overflow-hidden rounded-2xl bg-black">
        <video ref={video} className="h-full w-full object-cover" muted playsInline />
        <div className="pointer-events-none absolute inset-[18%] rounded-2xl border-2 border-white/80" />
      </div>
      <p className="text-[12.5px] text-[var(--sd-muted)]">{status}</p>
    </div>
  );
}
