/* QPH Comunicados & Bienvenidas studio. Self-contained (no virtual bundle). */
const { useState } = React;

const AREAS = [
  { key: "administracion", label: "Administración", hash: "ADMINISTRACIÓN", color: "#e7851a", soft: "#fbe7cf", ink: "#c96f12", dark: false },
  { key: "tecnologia", label: "Tecnología", hash: "TECNOLOGÍA", color: "#241d79", soft: "#e6e4f5", ink: "#241d79", dark: false },
  { key: "salud", label: "Salud", hash: "SALUD", color: "#15c0af", soft: "#e7f7f4", ink: "#0e8f82", dark: false },
  { key: "nomina", label: "Nómina", hash: "NÓMINA", color: "#f9c021", soft: "#fdf1cc", ink: "#8a6c00", dark: true },
  { key: "rsocial", label: "Responsabilidad Social", hash: "RSE", color: "#8467da", soft: "#ece7fa", ink: "#5b3fb0", dark: false },
  { key: "seguridad", label: "Seguridad de la Información", hash: "SEGURIDAD_INFORMACIÓN", color: "#003559", soft: "#d6e1ea", ink: "#003559", dark: false },
  { key: "proyectos", label: "Proyectos y Procesos", hash: "PROYECTOSYPROCESOS", color: "#253237", soft: "#dfe5e8", ink: "#253237", dark: false },
];

function Logo({ negative = false, height = 34 }) {
  const src = negative ? "../../assets/corporativo-logo-negativo.png" : "../../assets/corporativo-logo.png";
  return <img src={src} alt="corporativo." style={{ height: height * 0.72, width: "auto", display: "inline-block" }} />;
}

/* ---- Comunicado preview ---- */
function Comunicado({ area, msg, mail, format }) {
  const a = area;
  const wide = format === "wide";
  const footText = a.dark ? "#3d3d3d" : "#fff";
  return (
    <div className="art" style={{ width: wide ? 620 : 460, borderRadius: 18 }}>
      <div className="com-top">
        <Logo height={32} />
        <span className="com-htag" style={{ color: a.color }}>#{a.hash}</span>
      </div>
      <div className="com-center">
        <div className="com-q" style={{ color: a.color }}>&ldquo;</div>
        <p className="com-msg">{msg}</p>
        <div className="com-q" style={{ color: a.color, textAlign: "right" }}>&rdquo;</div>
      </div>
      <div className="com-foot" style={{ background: a.color, color: footText }}>
        <span>Más información</span>
        <span className="pill2" style={a.dark ? { borderColor: "rgba(61,61,61,.5)", color: "#3d3d3d" } : null}>{mail}</span>
      </div>
    </div>
  );
}

/* ---- Bienvenida preview ---- */
function Bienvenida({ area, name, role, format }) {
  const a = area;
  const wide = format === "wide";
  const ini = name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "QP";
  return (
    <div className="art bien" style={{ width: wide ? 620 : 460, borderRadius: 18, minHeight: wide ? 340 : 420, display: "flex", flexDirection: "column", justifyContent: "center" }}>
      <div className="logo-tl"><Logo height={30} /></div>
      <span className="bub" style={{ width: 28, height: 28, border: `3px solid ${a.color}`, top: 70, right: 90 }} />
      <span className="bub" style={{ width: 16, height: 16, border: `3px solid ${a.color}`, top: 150, left: 84 }} />
      <span className="bub" style={{ width: 10, height: 10, background: a.color, top: 110, right: 130 }} />
      <div className="ring" style={{ border: `8px solid ${a.color}` }}>
        <div className="ph" style={{ background: "linear-gradient(135deg,#c4c4c4,#6f6f6f)" }}>{ini}</div>
      </div>
      <h3 style={{ color: a.color }}>Bienvenida</h3>
      <div className="who">{name || "Nombre del colaborador"}</div>
      <div><span className="rolepill" style={{ border: `1px solid ${a.color}`, color: a.ink }}>{role || "Cargo"}</span></div>
    </div>
  );
}

function App() {
  const [tipo, setTipo] = useState("comunicado");
  const [areaKey, setAreaKey] = useState("tecnologia");
  const [format, setFormat] = useState("square");
  const [msg, setMsg] = useState("La transformación digital del edificio arranca este trimestre con nuevas herramientas internas.");
  const [mail, setMail] = useState("correo@qph.com.ec");
  const [name, setName] = useState("Ana Rafaela Ramírez");
  const [role, setRole] = useState("Consultor de RRHH");
  const area = AREAS.find((a) => a.key === areaKey);

  return (
    <div className="studio">
      <aside className="panel">
        <div>
          <h2>Estudio de marca</h2>
          <div className="lead">Comunicados y bienvenidas QPH</div>
        </div>

        <div className="group">
          <span className="gl">Tipo de pieza</span>
          <div className="seg">
            {[["comunicado", "Comunicado"], ["bienvenida", "Bienvenida"]].map(([k, l]) => (
              <button key={k} onClick={() => setTipo(k)}
                style={tipo === k ? { background: "#fff", color: "var(--qph-gray-700)", boxShadow: "var(--qph-shadow-sm)" } : null}>{l}</button>
            ))}
          </div>
        </div>

        <div className="group">
          <span className="gl">Área / empresa</span>
          <div className="chips">
            {AREAS.map((a) => {
              const on = a.key === areaKey;
              return (
                <button key={a.key} className="chip-a" onClick={() => setAreaKey(a.key)}
                  style={{ background: on ? a.color : a.soft, color: on ? (a.dark ? "#3d3d3d" : "#fff") : a.ink }}>
                  {a.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="group">
          <span className="gl">Formato</span>
          <div className="seg">
            {[["square", "Cuadrado"], ["wide", "Horizontal"]].map(([k, l]) => (
              <button key={k} onClick={() => setFormat(k)}
                style={format === k ? { background: "#fff", color: "var(--qph-gray-700)", boxShadow: "var(--qph-shadow-sm)" } : null}>{l}</button>
            ))}
          </div>
        </div>

        {tipo === "comunicado" ? (
          <React.Fragment>
            <div className="field"><label>Mensaje</label><textarea rows="4" value={msg} onChange={(e) => setMsg(e.target.value)} /></div>
            <div className="field"><label>Contacto</label><input value={mail} onChange={(e) => setMail(e.target.value)} /></div>
          </React.Fragment>
        ) : (
          <React.Fragment>
            <div className="field"><label>Nombre del colaborador</label><input value={name} onChange={(e) => setName(e.target.value)} /></div>
            <div className="field"><label>Cargo</label><input value={role} onChange={(e) => setRole(e.target.value)} /></div>
          </React.Fragment>
        )}

        <div className="lead" style={{ marginTop: "auto", borderTop: "1px solid var(--qph-border)", paddingTop: 14 }}>
          Mantenimiento: comunicados cada 6 meses · bienvenidas cada año.
        </div>
      </aside>

      <main className="stage">
        <div className="stage-inner">
          <span className="fmt-note">{tipo === "comunicado" ? "Comunicado" : "Bienvenida"} · {format === "square" ? "Cuadrado (feed)" : "Horizontal (banner)"} · #{area.hash}</span>
          {tipo === "comunicado"
            ? <Comunicado area={area} msg={msg} mail={mail} format={format} />
            : <Bienvenida area={area} name={name} role={role} format={format} />}
        </div>
      </main>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
