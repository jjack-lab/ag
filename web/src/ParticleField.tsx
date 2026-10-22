import type { CSSProperties } from "react";
import "./particle-field.css";

const particles = Array.from({ length: 72 }, (_, index) => ({
  x: `${(index * 73 + 19) % 100}%`,
  y: `${(index * 41 + Math.floor(index / 5) * 17) % 100}%`,
  delay: `${-((index * 7) % 13)}s`,
  duration: `${6 + index % 8}s`,
  size: `${2 + index % 4}px`,
}));

export default function ParticleField() {
  return <div className="particle-field" aria-hidden="true">
    <div className="particle-field-glow" />
    <div className="particle-field-grid" />
    {particles.map((particle, index) => <i key={index} style={{
      "--x": particle.x, "--y": particle.y, "--delay": particle.delay,
      "--duration": particle.duration, "--size": particle.size,
    } as CSSProperties} />)}
    <div className="particle-field-wave wave-one" /><div className="particle-field-wave wave-two" />
  </div>;
}
