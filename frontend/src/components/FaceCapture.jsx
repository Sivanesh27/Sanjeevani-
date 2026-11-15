import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, CheckCircle2, RefreshCw, ScanFace, ShieldCheck, TriangleAlert } from "lucide-react";
import { Button, Spinner } from "./ui";
import { cx } from "../lib/utils";

let faceapiPromise = null;
function loadFaceApi() {
  if (!faceapiPromise) {
    faceapiPromise = (async () => {
      const faceapi = await import("@vladmandic/face-api");
      await Promise.all([
        faceapi.nets.tinyFaceDetector.loadFromUri("/models"),
        faceapi.nets.faceLandmark68TinyNet.loadFromUri("/models"),
        faceapi.nets.faceRecognitionNet.loadFromUri("/models"),
      ]);
      return faceapi;
    })().catch((e) => { faceapiPromise = null; throw e; });
  }
  return faceapiPromise;
}

export const cameraSupported = () => typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && window.isSecureContext;
const dist = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
const ear = (p) => (dist(p[1], p[5]) + dist(p[2], p[4])) / (2 * dist(p[0], p[3]));
const yawOf = (p) => (p[30].x - (p[0].x + p[16].x) / 2) / (p[16].x - p[0].x);
const euclid = (a, b) => Math.sqrt(a.reduce((s, v, i) => s + (v - b[i]) ** 2, 0));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/**
 * mode="enroll": returns { descriptors:[d1,d2], photo }   mode="verify": returns { descriptor }
 * Flow: align -> capture #1 -> random liveness challenge (blink / turn head) -> capture #2 -> consistency check.
 */
export default function FaceCapture({ mode = "enroll", onDone, onCancel, compact }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const alive = useRef(true);
  const [phase, setPhase] = useState("loading");      // loading | live | done | error
  const [step, setStep] = useState(0);                 // 0 align, 1 challenge, 2 confirm
  const [msg, setMsg] = useState("Starting camera…");
  const [ok, setOk] = useState(false);
  const [err, setErr] = useState("");

  const stop = useCallback(() => { streamRef.current?.getTracks().forEach((t) => t.stop()); streamRef.current = null; }, []);

  const run = useCallback(async () => {
    alive.current = true; setPhase("loading"); setErr(""); setStep(0); setOk(false); setMsg("Starting camera…");
    if (!cameraSupported()) { setErr("Camera access needs a secure (HTTPS) connection and a supported browser."); setPhase("error"); return; }
    try {
      const [faceapi, stream] = await Promise.all([
        loadFaceApi(),
        navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }, audio: false }),
      ]);
      if (!alive.current) { stream.getTracks().forEach((t) => t.stop()); return; }
      streamRef.current = stream;
      const v = videoRef.current; v.srcObject = stream; v.setAttribute("playsinline", ""); v.muted = true;
      await v.play();
      setPhase("live");
      const opts = new faceapi.TinyFaceDetectorOptions({ inputSize: 224, scoreThreshold: 0.5 });
      const detect = () => faceapi.detectSingleFace(v, opts).withFaceLandmarks(true);
      const describe = async () => (await faceapi.detectSingleFace(v, opts).withFaceLandmarks(true).withFaceDescriptor());
      const snap = () => { const c = document.createElement("canvas"); const w = 320; c.width = w; c.height = Math.round((w * v.videoHeight) / v.videoWidth); c.getContext("2d").drawImage(v, 0, 0, c.width, c.height); return c.toDataURL("image/jpeg", 0.7); };

      const S = { stage: 0, stable: 0, d1: null, photo: null, challenge: Math.random() < 0.5 ? "blink" : "turn", cStart: 0, attempts: 0, ears: [], down: false, turned: false, restarts: 0 };
      setMsg("Look straight at the camera");
      while (alive.current) {
        await sleep(70);
        if (v.readyState < 2) continue;
        const det = await detect();
        if (!alive.current) return;
        if (!det) { S.stable = 0; setOk(false); setMsg(S.stage === 1 ? "Keep your face in view" : "No face found - face the camera in good light"); continue; }
        const box = det.detection.box, W = v.videoWidth;
        const size = box.width / W, cx = (box.x + box.width / 2) / W;
        const p = det.landmarks.positions, yaw = yawOf(p);
        const framed = size > 0.26 && size < 0.75 && Math.abs(cx - 0.5) < 0.2;
        setOk(framed);
        if (S.stage === 0 || S.stage === 2) {
          if (!framed) { S.stable = 0; setMsg(size <= 0.26 ? "Move a little closer" : size >= 0.75 ? "Move back a little" : "Centre your face in the oval"); continue; }
          if (Math.abs(yaw) > 0.12) { S.stable = 0; setMsg("Look straight at the camera"); continue; }
          S.stable += 1; setMsg("Hold still…");
          if (S.stable < 5) continue;
          const d = await describe(); if (!d) { S.stable = 0; continue; }
          if (S.stage === 0) {
            S.d1 = Array.from(d.descriptor); S.photo = snap(); S.stage = 1; S.stable = 0; S.cStart = Date.now(); setStep(1);
            setMsg(S.challenge === "blink" ? "Great. Now blink slowly" : "Great. Now turn your head slowly to one side, then back");
          } else {
            const d2 = Array.from(d.descriptor);
            if (euclid(S.d1, d2) > 0.5) { S.restarts += 1; if (S.restarts > 2) { setErr("We could not confirm a consistent face. Try again in better light."); setPhase("error"); stop(); return; } S.stage = 0; S.stable = 0; setStep(0); setMsg("Let's try that again - look straight"); continue; }
            stop(); setPhase("done");
            onDone(mode === "verify" ? { descriptor: d2 } : { descriptors: [S.d1, d2], photo: S.photo });
            return;
          }
        } else if (S.stage === 1) {
          if (Date.now() - S.cStart > 10000) {
            S.attempts += 1;
            if (S.attempts >= 3) { setErr("Liveness check was not completed. Please try again."); setPhase("error"); stop(); return; }
            S.challenge = S.challenge === "blink" ? "turn" : "blink"; S.cStart = Date.now(); S.ears = []; S.down = false; S.turned = false;
            setMsg(S.challenge === "blink" ? "Try again: blink slowly" : "Try again: turn your head to one side and back");
          }
          if (S.challenge === "blink") {
            const e = (ear(p.slice(36, 42)) + ear(p.slice(42, 48))) / 2; S.ears.push(e); if (S.ears.length > 14) S.ears.shift();
            const open = Math.max(...S.ears);
            if (e < open * 0.72) S.down = true;
            if (S.down && e > open * 0.86) { S.stage = 2; S.stable = 0; setStep(2); setMsg("Perfect. Look straight and hold still"); }
          } else {
            if (Math.abs(yaw) > 0.17) S.turned = true;
            if (S.turned && Math.abs(yaw) < 0.08) { S.stage = 2; S.stable = 0; setStep(2); setMsg("Perfect. Look straight and hold still"); }
          }
        }
      }
    } catch (e) {
      stop();
      const name = e?.name || "";
      setErr(name === "NotAllowedError" ? "Camera permission was denied. Allow camera access in your browser settings and try again."
        : name === "NotFoundError" ? "No camera was found on this device."
        : "Could not start the face check. Please refresh and try again.");
      setPhase("error");
    }
  }, [mode, onDone, stop]);

  useEffect(() => { run(); return () => { alive.current = false; stop(); }; }, [run, stop]);

  const steps = ["Align", "Liveness", "Confirm"];
  return (
    <div className="mx-auto w-full max-w-md">
      <div className={cx("relative overflow-hidden rounded-3xl bg-slate-950", compact ? "aspect-[4/5]" : "aspect-[3/4] sm:aspect-[4/3]")}>
        <video ref={videoRef} className="h-full w-full -scale-x-100 object-cover" playsInline muted autoPlay />
        {phase !== "error" && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center">
            <div className={cx("h-[72%] aspect-[3/4] rounded-[50%] border-[3px] transition-colors", ok ? "border-emerald-400 shadow-[0_0_0_9999px_rgba(2,6,23,.55)]" : "border-white/70 shadow-[0_0_0_9999px_rgba(2,6,23,.55)]")} />
          </div>)}
        {phase === "loading" && <div className="absolute inset-0 grid place-items-center bg-slate-950/70 text-white"><div className="flex items-center gap-3"><Spinner className="h-6 w-6" />{msg}</div></div>}
        {phase === "live" && <div className="absolute inset-x-3 bottom-3 rounded-2xl bg-slate-950/75 px-4 py-3 text-center text-[15px] font-semibold text-white backdrop-blur">{msg}</div>}
        {phase === "done" && <div className="absolute inset-0 grid place-items-center bg-emerald-600/90 text-white"><CheckCircle2 className="h-16 w-16" /></div>}
        {phase === "error" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 bg-slate-950 p-6 text-center text-white">
            <TriangleAlert className="h-10 w-10 text-amber-400" /><p className="text-sm">{err}</p>
            <Button variant="secondary" icon={RefreshCw} onClick={run}>Try again</Button>
          </div>)}
      </div>
      <div className="mt-4 flex items-center justify-center gap-2">
        {steps.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <span className={cx("grid h-6 w-6 place-items-center rounded-full text-xs font-bold", phase === "done" || i < step ? "bg-brand-600 text-onbrand" : i === step ? "border-2 border-brand-600 text-brand-600" : "bg-raised text-muted")}>{phase === "done" || i < step ? "✓" : i + 1}</span>
            <span className={cx("text-xs font-semibold", i === step ? "text-ink" : "text-muted")}>{s}</span>{i < 2 && <span className="mx-1 h-px w-5 bg-line" />}
          </div>))}
      </div>
      <p className="mt-3 flex items-start justify-center gap-1.5 text-center text-xs text-muted"><ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />Your face is processed on your device. Only a numeric face template and one small photo are sent, encrypted at rest.</p>
      {onCancel && <div className="mt-3 text-center"><button className="text-sm font-semibold text-muted hover:text-ink" onClick={() => { alive.current = false; stop(); onCancel(); }}>Cancel</button></div>}
    </div>
  );
}
export { ScanFace, Camera };
