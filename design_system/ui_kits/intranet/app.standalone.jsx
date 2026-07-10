/* QPH Intranet — interactive recreation. Self-contained (no virtual bundle). */
const { useState } = React;

const AREAS = [
  { key: "administracion", label: "Administración", hash: "ADMINISTRACIÓN", color: "#e7851a", soft: "#fbe7cf", ink: "#c96f12", icon: "briefcase" },
  { key: "tecnologia", label: "Tecnología", hash: "TECNOLOGÍA", color: "#241d79", soft: "#e6e4f5", ink: "#241d79", icon: "monitor" },
  { key: "salud", label: "Salud", hash: "SALUD", color: "#15c0af", soft: "#e7f7f4", ink: "#0e8f82", icon: "heart-pulse" },
  { key: "nomina", label: "Nómina", hash: "NÓMINA", color: "#f9c021", soft: "#fdf1cc", ink: "#8a6c00", icon: "wallet" },
  { key: "rsocial", label: "Responsabilidad Social", hash: "RSE", color: "#8467da", soft: "#ece7fa", ink: "#5b3fb0", icon: "hand-heart" },
  { key: "seguridad", label: "Seguridad de la Información", hash: "SEGURIDAD_INFORMACIÓN", color: "#003559", soft: "#d6e1ea", ink: "#003559", icon: "shield-check" },
  { key: "proyectos", label: "Proyectos y Procesos", hash: "PROYECTOSYPROCESOS", color: "#253237", soft: "#dfe5e8", ink: "#253237", icon: "git-branch" },
];
const areaBy = (k) => AREAS.find((a) => a.key === k) || AREAS[0];

const COMUNICADOS_SEED = [
  { id: 1, area: "tecnologia", msg: "La transformación digital del edificio arranca este trimestre con nuevas herramientas internas.", mail: "correo@qph.com.ec" },
  { id: 2, area: "salud", msg: "Jornada de chequeos médicos gratuitos para todos los colaboradores el próximo viernes.", mail: "salud@qph.com.ec" },
  { id: 3, area: "administracion", msg: "Recordatorio: actualiza tus datos de contacto en el portal antes de fin de mes.", mail: "correo@qph.com.ec" },
  { id: 4, area: "rsocial", msg: "Súmate a la campaña de reciclaje del edificio. Cada piso tendrá su punto verde.", mail: "rsocial@qph.com.ec" },
];

const PEOPLE = [
  { nm: "Ana Rafaela Ramírez", role: "Consultor de RRHH", area: "administracion", ini: "AR" },
  { nm: "Diego Salazar", role: "Ingeniero de Software", area: "tecnologia", ini: "DS" },
  { nm: "María Fernanda Coba", role: "Enfermera Ocupacional", area: "salud", ini: "MC" },
  { nm: "Luis Andrade", role: "Analista de Nómina", area: "nomina", ini: "LA" },
  { nm: "Paula Jiménez", role: "Coordinadora Social", area: "rsocial", ini: "PJ" },
  { nm: "Jorge Tipán", role: "Oficial de Seguridad TI", area: "seguridad", ini: "JT" },
];

const ICONS = {
  "briefcase": '<path d="M16 20V4a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" /> <rect width="20" height="14" x="2" y="6" rx="2" />',
  "monitor": '<rect width="20" height="14" x="2" y="3" rx="2" /> <line x1="8" x2="16" y1="21" y2="21" /> <line x1="12" x2="12" y1="17" y2="21" />',
  "heart-pulse": '<path d="M2 9.5a5.5 5.5 0 0 1 9.591-3.676.56.56 0 0 0 .818 0A5.49 5.49 0 0 1 22 9.5c0 2.29-1.5 4-3 5.5l-5.492 5.313a2 2 0 0 1-3 .019L5 15c-1.5-1.5-3-3.2-3-5.5" /> <path d="M3.22 13H9.5l.5-1 2 4.5 2-7 1.5 3.5h5.27" />',
  "wallet": '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1" /> <path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4" />',
  "hand-heart": '<path d="M11 14h2a2 2 0 0 0 0-4h-3c-.6 0-1.1.2-1.4.6L3 16" /> <path d="m14.45 13.39 5.05-4.694C20.196 8 21 6.85 21 5.75a2.75 2.75 0 0 0-4.797-1.837.276.276 0 0 1-.406 0A2.75 2.75 0 0 0 11 5.75c0 1.2.802 2.248 1.5 2.946L16 11.95" /> <path d="m2 15 6 6" /> <path d="m7 20 1.6-1.4c.3-.4.8-.6 1.4-.6h4c1.1 0 2.1-.4 2.8-1.2l4.6-4.4a1 1 0 0 0-2.75-2.91" />',
  "shield-check": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" /> <path d="m9 12 2 2 4-4" />',
  "git-branch": '<path d="M15 6a9 9 0 0 0-9 9V3" /> <circle cx="18" cy="6" r="3" /> <circle cx="6" cy="18" r="3" />',
  "layout-dashboard": '<rect width="7" height="9" x="3" y="3" rx="1" /> <rect width="7" height="5" x="14" y="3" rx="1" /> <rect width="7" height="9" x="14" y="12" rx="1" /> <rect width="7" height="5" x="3" y="16" rx="1" />',
  "megaphone": '<path d="M11 6a13 13 0 0 0 8.4-2.8A1 1 0 0 1 21 4v12a1 1 0 0 1-1.6.8A13 13 0 0 0 11 14H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2z" /> <path d="M6 14a12 12 0 0 0 2.4 7.2 2 2 0 0 0 3.2-2.4A8 8 0 0 1 10 14" /> <path d="M8 6v8" />',
  "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" /> <path d="M16 3.128a4 4 0 0 1 0 7.744" /> <path d="M22 21v-2a4 4 0 0 0-3-3.87" /> <circle cx="9" cy="7" r="4" />',
  "layout-grid": '<rect width="7" height="7" x="3" y="3" rx="1" /> <rect width="7" height="7" x="14" y="3" rx="1" /> <rect width="7" height="7" x="14" y="14" rx="1" /> <rect width="7" height="7" x="3" y="14" rx="1" />',
  "search": '<path d="m21 21-4.34-4.34" /> <circle cx="11" cy="11" r="8" />',
  "arrow-right": '<path d="M5 12h14" /> <path d="m12 5 7 7-7 7" />',
  "plus": '<path d="M5 12h14" /> <path d="M12 5v14" />',
  "log-out": '<path d="m16 17 5-5-5-5" /> <path d="M21 12H9" /> <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />',
  "x": '<path d="M18 6 6 18" /> <path d="m6 6 12 12" />',
};
function Icon({ name, size = 18, style }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={style}
      dangerouslySetInnerHTML={{ __html: ICONS[name] || "" }} />
  );
}

/* ---------------- Logo (CSS recreation) ---------------- */
function Logo({ negative = false, height = 40, name = true }) {
  const src = negative ? window.__resources.logoNeg : window.__resources.logoPos;
  return <img src={src} alt="corporativo." style={{ height: height * 0.72, width: "auto", display: "inline-block" }} />;
}

/* ---------------- Login ---------------- */
function Login({ onEnter }) {
  return (
    <div className="login">
      <div className="login-art">
        <span className="arc a1"></span><span className="arc a2"></span><span className="dot"></span>
        <h2>Portal del<br /><em>Edificio</em> QPH</h2>
      </div>
      <div className="login-form">
        <div className="inner">
          <Logo height={46} />
          <div>
            <h1 style={{ fontSize: 26, fontWeight: 900, textTransform: "uppercase" }}>Iniciar sesión</h1>
            <p className="muted">Accede con tu correo corporativo @qph.com.ec</p>
          </div>
          <div className="field"><label>Correo</label><input defaultValue="ana.ramirez@qph.com.ec" /></div>
          <div className="field"><label>Contraseña</label><input type="password" defaultValue="••••••••" /></div>
          <button className="btn btn-primary" style={{ justifyContent: "center" }} onClick={onEnter}>Entrar</button>
          <p className="muted" style={{ textAlign: "center" }}>¿Olvidaste tu clave? Contacta a Tecnología.</p>
        </div>
      </div>
    </div>
  );
}

/* ---------------- Sidebar ---------------- */
function Sidebar({ screen, go }) {
  const items = [
    { k: "inicio", label: "Inicio", icon: "layout-dashboard" },
    { k: "comunicados", label: "Comunicados", icon: "megaphone" },
    { k: "colaboradores", label: "Colaboradores", icon: "users" },
    { k: "areas", label: "Áreas", icon: "layout-grid" },
  ];
  return (
    <aside className="sidebar">
      <div className="side-brand"><Logo negative height={40} /></div>
      <nav className="nav">
        <div className="nav-section">Menú</div>
        {items.map((it) => {
          const active = screen === it.k;
          return (
            <button
              key={it.k}
              className={"nav-item" + (active ? " active" : "")}
              style={active ? { background: "var(--qph-orange)", color: "#fff" } : undefined}
              onClick={() => go(it.k)}
            >
              <Icon name={it.icon} /> {it.label}
            </button>
          );
        })}
      </nav>
      <div className="side-foot">
        <span className="tile" style={{ width: 36, height: 36, background: "#e7851a", borderRadius: 999, fontFamily: "var(--qph-font-display)", fontWeight: 900, fontSize: 14 }}>AR</span>
        <div style={{ flex: 1, minWidth: 0 }}><div className="who">Ana Ramírez</div><div className="role">Administración</div></div>
      </div>
    </aside>
  );
}

/* ---------------- Topbar ---------------- */
function Topbar({ title, crumb, action }) {
  return (
    <header className="topbar">
      <div>
        <div className="crumb">{crumb}</div>
        <h1>{title}</h1>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div className="search"><Icon name="search" style={{ width: 16, height: 16 }} /><input placeholder="Buscar…" /></div>
        {action}
      </div>
    </header>
  );
}

/* ---------------- Comunicado card ---------------- */
function Comunicado({ c }) {
  const a = areaBy(c.area);
  return (
    <article className="com">
      <div className="com-top">
        <Logo height={26} name={false} />
        <span className="com-htag" style={{ color: a.color }}>#{a.hash}</span>
      </div>
      <div className="com-body">
        <div className="com-quote" style={{ color: a.color }}>&ldquo;</div>
        <p className="com-msg">{c.msg}</p>
      </div>
      <div className="com-foot" style={{ background: a.color, color: a.key === "nomina" ? "#3d3d3d" : "#fff" }}>
        <span>Más información</span>
        <span className="pill2" style={a.key === "nomina" ? { borderColor: "rgba(61,61,61,.5)", color: "#3d3d3d" } : null}>{c.mail}</span>
      </div>
    </article>
  );
}

/* ---------------- Screens ---------------- */
function Dashboard({ go }) {
  return (
    <div className="content">
      <div className="eyebrow"><span className="sec">Resumen</span><span className="bar"></span><span className="ttl">Hoy en el edificio</span></div>
      <div className="stats">
        <div className="stat"><div className="num">128</div><div className="cap">Colaboradores</div></div>
        <div className="stat"><div className="num">7</div><div className="cap">Áreas</div></div>
        <div className="stat"><div className="num">12</div><div className="cap">Empresas</div></div>
        <div className="stat"><div className="num">98%</div><div className="cap">Satisfacción</div></div>
      </div>
      <div className="card">
        <div className="card-h"><h3>Comunicados recientes</h3><button className="btn btn-ghost btn-sm" onClick={() => go("comunicados")}>Ver todos <Icon name="arrow-right" /></button></div>
        <div className="feed">
          {COMUNICADOS_SEED.slice(0, 2).map((c) => <Comunicado key={c.id} c={c} />)}
        </div>
      </div>
      <div className="card">
        <div className="card-h"><h3>Áreas del edificio</h3></div>
        <div className="areas">
          {AREAS.map((a) => (
            <div key={a.key} className="area" style={{ background: a.color, color: a.key === "nomina" ? "#3d3d3d" : "#fff" }} onClick={() => go("comunicados")}>
              <span className="tile" style={{ background: "rgba(255,255,255,.18)" }}><Icon name={a.icon} /></span>
              <span className="an">{a.label}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Comunicados({ filter, setFilter }) {
  const list = filter === "all" ? COMUNICADOS_SEED : COMUNICADOS_SEED.filter((c) => c.area === filter);
  return (
    <div className="content">
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button className={"tag"} style={{ cursor: "pointer", background: filter === "all" ? "#595756" : "#f2f2f2", color: filter === "all" ? "#fff" : "#787474" }} onClick={() => setFilter("all")}>Todas</button>
        {AREAS.map((a) => (
          <button key={a.key} className="tag" style={{ cursor: "pointer", background: filter === a.key ? a.color : a.soft, color: filter === a.key ? (a.key === "nomina" ? "#3d3d3d" : "#fff") : a.ink }} onClick={() => setFilter(a.key)}>{a.label}</button>
        ))}
      </div>
      <div className="feed">
        {list.map((c) => <Comunicado key={c.id} c={c} />)}
      </div>
      {list.length === 0 && <p className="muted">No hay comunicados para esta área todavía.</p>}
    </div>
  );
}

function Colaboradores() {
  return (
    <div className="content">
      <div className="eyebrow"><span className="sec">Equipo</span><span className="bar"></span><span className="ttl">Colaboradores</span></div>
      <div className="people">
        {PEOPLE.map((p) => {
          const a = areaBy(p.area);
          return (
            <div key={p.nm} className="person">
              <span className="bub" style={{ width: 20, height: 20, top: 30, right: 44 }}></span>
              <span className="bub" style={{ width: 12, height: 12, top: 84, left: 50 }}></span>
              <div className="ring" style={{ borderColor: a.color }}>
                <div className="ph" style={{ background: "linear-gradient(135deg,#bdbdbd,#7a7a7a)" }}>{p.ini}</div>
              </div>
              <div className="nm">{p.nm}</div>
              <div style={{ marginTop: 8 }}><span className="pill" style={{ borderColor: a.color, color: a.ink }}>{p.role}</span></div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Areas() {
  return (
    <div className="content">
      <div className="eyebrow"><span className="sec">Servicios</span><span className="bar"></span><span className="ttl">Áreas corporativas</span></div>
      <div className="areas" style={{ gridTemplateColumns: "repeat(3,1fr)" }}>
        {AREAS.map((a) => (
          <div key={a.key} className="area" style={{ background: a.color, color: a.key === "nomina" ? "#3d3d3d" : "#fff", minHeight: 140 }}>
            <span className="tile" style={{ background: "rgba(255,255,255,.18)" }}><Icon name={a.icon} /></span>
            <div>
              <span className="an">{a.label}</span>
              <div className="ac" style={{ marginTop: 4, fontFamily: "monospace" }}>{a.color}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ---------------- New comunicado modal ---------------- */
function NewModal({ onClose }) {
  const [area, setArea] = useState("administracion");
  return (
    <div className="scrim" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-h"><h3>Nuevo comunicado</h3><button className="iconbtn" onClick={onClose}><Icon name="x" /></button></div>
        <div className="modal-b">
          <div className="field"><label>Área</label>
            <select value={area} onChange={(e) => setArea(e.target.value)}>
              {AREAS.map((a) => <option key={a.key} value={a.key}>{a.label}</option>)}
            </select>
          </div>
          <div className="field"><label>Mensaje</label><textarea rows="3" placeholder="Escribe el comunicado…" defaultValue="" /></div>
          <div className="field"><label>Contacto</label><input defaultValue="correo@qph.com.ec" /></div>
          <div style={{ display: "flex", justifyContent: "center" }}>
            <span className="tag" style={{ background: areaBy(area).soft, color: areaBy(area).ink }}>Vista previa: #{areaBy(area).hash}</span>
          </div>
        </div>
        <div className="modal-f">
          <button className="btn btn-secondary" onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" onClick={onClose}>Publicar</button>
        </div>
      </div>
    </div>
  );
}

/* ---------------- App ---------------- */
function App() {
  const [auth, setAuth] = useState(false);
  const [screen, setScreen] = useState("inicio");
  const [filter, setFilter] = useState("all");
  const [modal, setModal] = useState(false);


  if (!auth) return <Login onEnter={() => setAuth(true)} />;

  const titles = {
    inicio: { t: "Inicio", c: "Panel del edificio" },
    comunicados: { t: "Comunicados", c: "Difusión interna" },
    colaboradores: { t: "Colaboradores", c: "Directorio" },
    areas: { t: "Áreas", c: "Servicios corporativos" },
  };
  const meta = titles[screen];
  const action = screen === "comunicados"
    ? <button className="btn btn-primary" onClick={() => setModal(true)}><Icon name="plus" /> Nuevo comunicado</button>
    : <button className="btn btn-secondary btn-sm" onClick={() => setAuth(false)}><Icon name="log-out" /> Salir</button>;

  return (
    <div className="app">
      <Sidebar screen={screen} go={setScreen} />
      <div className="main">
        <Topbar title={meta.t} crumb={meta.c} action={action} />
        {screen === "inicio" && <Dashboard go={setScreen} />}
        {screen === "comunicados" && <Comunicados filter={filter} setFilter={setFilter} />}
        {screen === "colaboradores" && <Colaboradores />}
        {screen === "areas" && <Areas />}
      </div>
      {modal && <NewModal onClose={() => setModal(false)} />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
