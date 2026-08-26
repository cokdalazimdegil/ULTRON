import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { EffectComposer } from "three/addons/postprocessing/EffectComposer.js";
import { RenderPass } from "three/addons/postprocessing/RenderPass.js";
import { UnrealBloomPass } from "three/addons/postprocessing/UnrealBloomPass.js";

const HOME_POSITION = new THREE.Vector3(0, 0, 5.5);
const MIN_DISTANCE  = 2.0;
const MAX_DISTANCE  = 40;

export function createOrbScene(container) {
    const width  = container.clientWidth  || window.innerWidth;
    const height = container.clientHeight || window.innerHeight;

    // ── SCENE & CAMERA ───────────────────────────────────────────────────────
    const scene    = new THREE.Scene();
    const camera   = new THREE.PerspectiveCamera(55, width / height, 0.1, 500);
    camera.position.copy(HOME_POSITION);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 0.85;
    container.appendChild(renderer.domElement);

    // ── POST PROCESSING ──────────────────────────────────────────────────────
    const composer = new EffectComposer(renderer);
    composer.addPass(new RenderPass(scene, camera));
    const bloom = new UnrealBloomPass(new THREE.Vector2(width, height), 1.8, 0.4, 0.2);
    composer.addPass(bloom);

    // ── ORBIT CONTROLS ───────────────────────────────────────────────────────
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping  = true;
    controls.dampingFactor  = 0.04;
    controls.minDistance    = MIN_DISTANCE;
    controls.maxDistance    = MAX_DISTANCE;
    controls.enablePan      = false;

    // ── UI CONFIGURATION & SENSITIVITY ───────────────────────────────────────
    const UI_CONFIG = {
        animationIntensity: 1.0,
        particleDensity: 1.0,
        glowIntensity: 1.0,
        transitionSpeed: 1.0,
        reducedMotion: false,
    };

    // ── COMPLETE 15-STATE CINEMATIC COLOR & ENERGY PALETTE ───────────────────
    const STATE_COLORS = {
        IDLE:             { core: 0xff6600, glow: 0xff3300, shell: 0x884400, bloom: 1.4, ring: 0xff6600, meridian: 0xffaa30, neural: 0xffaa44 },
        LISTENING:        { core: 0x00ccff, glow: 0x0099ff, shell: 0x003366, bloom: 2.2, ring: 0x00ccff, meridian: 0x00eeff, neural: 0x00ffff },
        THINKING:         { core: 0xff9900, glow: 0xff5500, shell: 0x664400, bloom: 2.4, ring: 0xff9900, meridian: 0xffcc00, neural: 0xffaa00 },
        EXECUTING:        { core: 0x0088ff, glow: 0x0055ff, shell: 0x002266, bloom: 2.6, ring: 0x0088ff, meridian: 0x33bbff, neural: 0x00aaff },
        OBSERVING:        { core: 0x00ffcc, glow: 0x00cc99, shell: 0x004433, bloom: 2.0, ring: 0x00ffcc, meridian: 0x66ffdd, neural: 0x00ffcc },
        SPEAKING:         { core: 0x00ff88, glow: 0x00cc66, shell: 0x004422, bloom: 2.5, ring: 0x00ff88, meridian: 0x44ffaa, neural: 0x00ff99 },
        SUCCESS:          { core: 0x00ffaa, glow: 0xffd700, shell: 0x006644, bloom: 2.8, ring: 0xffd700, meridian: 0x66ffbb, neural: 0xffea00 },
        WARNING:          { core: 0xffaa00, glow: 0xff7700, shell: 0x664400, bloom: 2.2, ring: 0xffaa00, meridian: 0xffcc44, neural: 0xff8800 },
        ERROR:            { core: 0xff1133, glow: 0xcc0022, shell: 0x550011, bloom: 2.8, ring: 0xff2244, meridian: 0xff4466, neural: 0xff2244 },
        CONFIRMING:       { core: 0xffaa22, glow: 0xff6600, shell: 0x664400, bloom: 2.3, ring: 0xffaa22, meridian: 0xffdd66, neural: 0xff9900 },
        UNKNOWN_SPEAKER:  { core: 0x8899aa, glow: 0x556677, shell: 0x223344, bloom: 1.8, ring: 0x8899aa, meridian: 0xaabbcc, neural: 0x778899 },
        VERIFIED_NURI:    { core: 0xff6600, glow: 0xff3300, shell: 0x884400, bloom: 2.7, ring: 0xffaa30, meridian: 0xffcc44, neural: 0xff8800 },
        VERIFIED_RABIA:   { core: 0xff3399, glow: 0xcc0066, shell: 0x660033, bloom: 2.7, ring: 0xff66bb, meridian: 0xff99dd, neural: 0xff3399 },
        CONNECTING:       { core: 0x4466ff, glow: 0x2244cc, shell: 0x112266, bloom: 1.8, ring: 0x4466ff, meridian: 0x6688ff, neural: 0x4466ff },
        DISCONNECTED:     { core: 0x663322, glow: 0x331100, shell: 0x221100, bloom: 0.8, ring: 0x663322, meridian: 0x884433, neural: 0x552211 },
    };

    let aiState            = "IDLE";
    let currentBloom       = 1.4;
    let targetBloom        = 1.4;
    let currentCoreColor   = new THREE.Color(0xff6600);
    let targetCoreColor    = new THREE.Color(0xff6600);
    let currentGlowColor   = new THREE.Color(0xff3300);
    let targetGlowColor    = new THREE.Color(0xff3300);
    let currentRingColor   = new THREE.Color(0xff6600);
    let targetRingColor    = new THREE.Color(0xff6600);
    let currentNeuralColor = new THREE.Color(0xffaa44);
    let targetNeuralColor  = new THREE.Color(0xffaa44);

    // Audio-visual live synchronization levels
    let liveMicEnergy      = 0.0;
    let liveSpeakerEnergy  = 0.0;

    // ── HELPERS ──────────────────────────────────────────────────────────────
    function lineMat(color, opacity) {
        var op = (opacity === undefined) ? 1 : opacity;
        return new THREE.LineBasicMaterial({
            color: color, transparent: true, opacity: op,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
        });
    }
    function latRing(radius, lat, segs) {
        var s = segs || 100;
        var r = radius * Math.cos(lat);
        var y = radius * Math.sin(lat);
        var pts = [];
        for (var i = 0; i <= s; i++) {
            var a = (i / s) * Math.PI * 2;
            pts.push(new THREE.Vector3(r * Math.cos(a), y, r * Math.sin(a)));
        }
        return new THREE.BufferGeometry().setFromPoints(pts);
    }
    function meridian(radius, lon, segs) {
        var s = segs || 100;
        var pts = [];
        for (var i = 0; i <= s; i++) {
            var lat = (i / s) * Math.PI - Math.PI / 2;
            pts.push(new THREE.Vector3(
                radius * Math.cos(lat) * Math.cos(lon),
                radius * Math.sin(lat),
                radius * Math.cos(lat) * Math.sin(lon)
            ));
        }
        return new THREE.BufferGeometry().setFromPoints(pts);
    }

    const orbGroup = new THREE.Group();
    scene.add(orbGroup);

    // ── LAYER 0: ENERGY FIELD — large semi-transparent outer sphere ──────────
    var R_FIELD = 2.6;
    var energyFieldMat = new THREE.MeshBasicMaterial({
        color: 0xff6600,
        transparent: true,
        opacity: 0.03,
        blending: THREE.AdditiveBlending,
        side: THREE.BackSide,
        depthWrite: false,
    });
    var energyField = new THREE.Mesh(
        new THREE.SphereGeometry(R_FIELD, 32, 32),
        energyFieldMat
    );
    orbGroup.add(energyField);

    // ── LAYER 1: OUTER WIREFRAME SHELL ───────────────────────────────────────
    const outerShell = new THREE.Group();
    const R1 = 2.0;
    for (let i = -10; i <= 10; i++) {
        const lat     = (i / 10) * (Math.PI / 2) * 0.95;
        const isMajor = i % 5 === 0;
        outerShell.add(new THREE.Line(
            latRing(R1, lat),
            lineMat(isMajor ? 0xdd7700 : 0x553300, isMajor ? 0.5 : 0.12)
        ));
    }
    for (let i = 0; i < 4; i++) {
        const lon = (i / 4) * Math.PI * 2;
        outerShell.add(new THREE.Line(meridian(R1, lon), lineMat(0xffaa30, 0.8)));
    }
    for (let i = 0; i < 12; i++) {
        const lon = (i / 12) * Math.PI * 2;
        outerShell.add(new THREE.Line(meridian(R1, lon), lineMat(0x553300, 0.12)));
    }
    orbGroup.add(outerShell);

    // ── LAYER 1.5: SECONDARY OFFSET SHELL ───────────────────────────────────
    const shell2 = new THREE.Group();
    const R2     = 2.15;
    for (let i = 0; i < 10; i++) {
        const lat = (Math.random() - 0.5) * Math.PI * 0.8;
        const lon = Math.random() * Math.PI * 2;
        const arc = 0.5 + Math.random() * 1.2;
        const pts = [];
        const r   = R2 * Math.cos(lat);
        const y   = R2 * Math.sin(lat);
        for (let j = 0; j <= 60; j++) {
            const a = lon + (j / 60) * arc;
            pts.push(new THREE.Vector3(r * Math.cos(a), y, r * Math.sin(a)));
        }
        shell2.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(pts),
            lineMat(0xdd7700, 0.2 + Math.random() * 0.25)
        ));
    }
    orbGroup.add(shell2);

    // ── LAYER 2: MAJOR ARC MERIDIAN BEAMS ───────────────────────────────────
    var meridianGroup = new THREE.Group();
    var meridianLines = [];
    var R_MERIDIAN = 2.05;
    for (var mi = 0; mi < 4; mi++) {
        var mlon = (mi / 4) * Math.PI * 2;
        var mmat = new THREE.LineBasicMaterial({
            color: 0xffaa30,
            transparent: true,
            opacity: 0.85,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
        });
        var mline = new THREE.Line(meridian(R_MERIDIAN, mlon, 120), mmat);
        meridianGroup.add(mline);
        meridianLines.push({ line: mline, mat: mmat });
    }
    orbGroup.add(meridianGroup);

    // ── LAYER 3: INNER GEODESIC SHELL ────────────────────────────────────────
    const innerCore = new THREE.Group();
    const R3        = 0.9;
    for (let s = 0; s < 6; s++) {
        const pts  = [];
        const segs = 200;
        const turns = 3 + s * 0.5;
        const phase = (s / 6) * Math.PI * 2;
        for (let i = 0; i <= segs; i++) {
            const t   = i / segs;
            const lat = t * Math.PI - Math.PI / 2;
            const lon = t * turns * Math.PI * 2 + phase;
            pts.push(new THREE.Vector3(
                R3 * Math.cos(lat) * Math.cos(lon),
                R3 * Math.sin(lat),
                R3 * Math.cos(lat) * Math.sin(lon)
            ));
        }
        innerCore.add(new THREE.Line(
            new THREE.BufferGeometry().setFromPoints(pts),
            lineMat(0xffaa30, 0.3 + Math.random() * 0.2)
        ));
    }
    for (let i = -5; i <= 5; i++) {
        const lat = (i / 5) * (Math.PI / 2) * 0.9;
        innerCore.add(new THREE.Line(latRing(R3, lat, 60), lineMat(0x884400, 0.2)));
    }
    orbGroup.add(innerCore);

    // ── LAYER 4: BRIGHT CORE (Icosahedron + sphere) ──────────────────────────
    const icoGeo    = new THREE.IcosahedronGeometry(0.25, 1);
    const icoEdges  = new THREE.EdgesGeometry(icoGeo);
    const icoWireMat = lineMat(0xffcc66, 0.9);
    const icoWire   = new THREE.LineSegments(icoEdges, icoWireMat);
    orbGroup.add(icoWire);

    const coreSphereMat = new THREE.MeshBasicMaterial({
        color: 0xffcc66, transparent: true, opacity: 0.15,
        blending: THREE.AdditiveBlending,
    });
    const coreSphere = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 16), coreSphereMat);
    orbGroup.add(coreSphere);

    const glowSphereMat = new THREE.MeshBasicMaterial({
        color: 0xdd7700, transparent: true, opacity: 0.04,
        blending: THREE.AdditiveBlending,
    });
    const glowSphere = new THREE.Mesh(new THREE.SphereGeometry(0.5, 12, 12), glowSphereMat);
    orbGroup.add(glowSphere);

    // ── LAYER 5: NEURAL SYNAPSE & BRAIN NEURON SYSTEM ────────────────────────
    const neuralGroup = new THREE.Group();
    orbGroup.add(neuralGroup);

    const NEURAL_NODE_COUNT = 48;
    const neuralNodes = [];
    const nodeGeometry = new THREE.SphereGeometry(0.018, 8, 8);
    const nodeMaterial = new THREE.MeshBasicMaterial({
        color: 0xffaa44,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending,
    });

    for (let ni = 0; ni < NEURAL_NODE_COUNT; ni++) {
        const radius = 0.45 + Math.pow(Math.random(), 0.7) * 1.35;
        const theta = Math.random() * Math.PI * 2;
        const phi   = Math.acos(2 * Math.random() - 1);
        
        const pos = new THREE.Vector3(
            radius * Math.sin(phi) * Math.cos(theta),
            radius * Math.sin(phi) * Math.sin(theta),
            radius * Math.cos(phi)
        );

        const nodeMesh = new THREE.Mesh(nodeGeometry, nodeMaterial.clone());
        nodeMesh.position.copy(pos);
        neuralGroup.add(nodeMesh);

        neuralNodes.push({
            mesh: nodeMesh,
            pos: pos.clone(),
            basePos: pos.clone(),
            phase: Math.random() * Math.PI * 2,
            speed: 0.3 + Math.random() * 0.7,
            energy: Math.random(),
            connections: [],
        });
    }

    const axonPairs = [];
    const axonPoints = [];
    const MAX_AXON_DIST = 0.95;

    for (let i = 0; i < neuralNodes.length; i++) {
        for (let j = i + 1; j < neuralNodes.length; j++) {
            const dist = neuralNodes[i].pos.distanceTo(neuralNodes[j].pos);
            if (dist < MAX_AXON_DIST) {
                axonPairs.push([i, j]);
                axonPoints.push(neuralNodes[i].pos.x, neuralNodes[i].pos.y, neuralNodes[i].pos.z);
                axonPoints.push(neuralNodes[j].pos.x, neuralNodes[j].pos.y, neuralNodes[j].pos.z);
                neuralNodes[i].connections.push(j);
                neuralNodes[j].connections.push(i);
            }
        }
    }

    const axonGeo = new THREE.BufferGeometry();
    axonGeo.setAttribute("position", new THREE.Float32BufferAttribute(new Float32Array(axonPoints), 3));
    const axonMat = new THREE.LineBasicMaterial({
        color: 0xffaa44,
        transparent: true,
        opacity: 0.25,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
    });
    const axonLines = new THREE.LineSegments(axonGeo, axonMat);
    neuralGroup.add(axonLines);

    // Neural Action Potential Sparks
    const SPARK_COUNT = 24;
    const neuralSparks = [];
    const sparkGeo = new THREE.SphereGeometry(0.015, 6, 6);
    const sparkMat = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.95,
        blending: THREE.AdditiveBlending,
    });

    for (let si = 0; si < SPARK_COUNT; si++) {
        const pair = axonPairs[Math.floor(Math.random() * axonPairs.length)] || [0, 1];
        const sparkMesh = new THREE.Mesh(sparkGeo, sparkMat.clone());
        neuralGroup.add(sparkMesh);
        neuralSparks.push({
            mesh: sparkMesh,
            fromNode: pair[0],
            toNode: pair[1],
            progress: Math.random(),
            speed: 0.015 + Math.random() * 0.035,
        });
    }

    // Neural Arc Discharges
    const ARC_COUNT = 6;
    const arcGeo = new THREE.BufferGeometry();
    const arcPositions = new Float32Array(ARC_COUNT * 8 * 3);
    arcGeo.setAttribute("position", new THREE.BufferAttribute(arcPositions, 3));
    const arcMat = new THREE.LineBasicMaterial({
        color: 0xffcc44,
        transparent: true,
        opacity: 0,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
    });
    const arcLineSegments = new THREE.LineSegments(arcGeo, arcMat);
    neuralGroup.add(arcLineSegments);

    // ── PULSING ENERGY RING (equator) ────────────────────────────────────────
    var energyRingMat = new THREE.MeshBasicMaterial({
        color: 0xff6600,
        transparent: true,
        opacity: 0.55,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    var energyRingGeo = new THREE.TorusGeometry(R1, 0.025, 16, 120);
    var energyRing = new THREE.Mesh(energyRingGeo, energyRingMat);
    energyRing.rotation.x = Math.PI / 2;
    orbGroup.add(energyRing);

    var energyRing2Mat = new THREE.MeshBasicMaterial({
        color: 0xffcc44,
        transparent: true,
        opacity: 0.3,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    var energyRing2 = new THREE.Mesh(
        new THREE.TorusGeometry(R1 * 0.85, 0.012, 12, 100),
        energyRing2Mat
    );
    energyRing2.rotation.x = Math.PI / 2;
    orbGroup.add(energyRing2);

    // ── SPECIAL STATE VISUAL LAYER 1: CINEMATIC SHOCKWAVE FLARE (SUCCESS/VERIFIED) ─
    const shockwaveMat = new THREE.MeshBasicMaterial({
        color: 0xffffff,
        transparent: true,
        opacity: 0.0,
        blending: THREE.AdditiveBlending,
        side: THREE.DoubleSide,
        depthWrite: false,
    });
    const shockwaveRing = new THREE.Mesh(new THREE.TorusGeometry(R1 * 0.4, 0.04, 16, 100), shockwaveMat);
    shockwaveRing.rotation.x = Math.PI / 2;
    orbGroup.add(shockwaveRing);

    let shockwaveActive   = false;
    let shockwaveProgress = 1.0;
    let shockwaveColor    = new THREE.Color(0xffd700);

    function triggerShockwave(hexColor = 0xffd700) {
        shockwaveColor.setHex(hexColor);
        shockwaveProgress = 0.0;
        shockwaveActive = true;
    }

    // ── SPECIAL STATE VISUAL LAYER 2: OPTICAL VISION RETICLE (OBSERVING) ─────
    const reticleGroup = new THREE.Group();
    const reticleMat = new THREE.LineBasicMaterial({
        color: 0x00ffcc,
        transparent: true,
        opacity: 0.0,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
    });

    const reticleRing = new THREE.Line(latRing(R1 * 1.25, 0, 80), reticleMat);
    reticleGroup.add(reticleRing);

    // 4 Corner Brackets for Optical Target Lock
    const bracketSize = 0.35;
    const bracketDist = R1 * 1.15;
    const bracketPts = [];
    const corners = [
        [bracketDist, bracketDist],
        [-bracketDist, bracketDist],
        [-bracketDist, -bracketDist],
        [bracketDist, -bracketDist]
    ];
    corners.forEach(([cx, cy]) => {
        const sx = cx > 0 ? -1 : 1;
        const sy = cy > 0 ? -1 : 1;
        bracketPts.push(new THREE.Vector3(cx, cy, 0));
        bracketPts.push(new THREE.Vector3(cx + sx * bracketSize, cy, 0));
        bracketPts.push(new THREE.Vector3(cx, cy, 0));
        bracketPts.push(new THREE.Vector3(cx, cy + sy * bracketSize, 0));
    });
    const bracketGeo = new THREE.BufferGeometry().setFromPoints(bracketPts);
    const bracketLines = new THREE.LineSegments(bracketGeo, reticleMat);
    reticleGroup.add(bracketLines);
    orbGroup.add(reticleGroup);

    // ── SPECIAL STATE VISUAL LAYER 3: DIRECTIONAL PLASMA FLUX (EXECUTING) ────
    const plasmaGroup = new THREE.Group();
    const PLASMA_COUNT = 36;
    const plasmaDots = [];
    const plasmaGeo = new THREE.SphereGeometry(0.022, 6, 6);
    const plasmaMat = new THREE.MeshBasicMaterial({
        color: 0x33bbff,
        transparent: true,
        opacity: 0.0,
        blending: THREE.AdditiveBlending,
    });
    for (let pi = 0; pi < PLASMA_COUNT; pi++) {
        const pmesh = new THREE.Mesh(plasmaGeo, plasmaMat.clone());
        plasmaGroup.add(pmesh);
        plasmaDots.push({
            mesh: pmesh,
            radius: R1 * (0.6 + Math.random() * 0.6),
            theta: Math.random() * Math.PI * 2,
            speed: 2.2 + Math.random() * 2.8,
            altitude: (Math.random() - 0.5) * 0.4,
        });
    }
    orbGroup.add(plasmaGroup);

    // ── HEXAGONAL GRID PANEL (arc reactor surface grid) ──────────────────────
    var hexGroup = new THREE.Group();
    var HEX_R = R1 * 0.99;
    var hexSize = 0.18;

    function buildHexPoints(cx, cy, cz, nx, ny, nz, size) {
        var nv = new THREE.Vector3(nx, ny, nz).normalize();
        var up = new THREE.Vector3(0, 1, 0);
        if (Math.abs(nv.dot(up)) > 0.9) up.set(1, 0, 0);
        var tangent  = new THREE.Vector3().crossVectors(up, nv).normalize();
        var bitangent = new THREE.Vector3().crossVectors(nv, tangent).normalize();
        var pts = [];
        for (var k = 0; k <= 6; k++) {
            var angle = (k / 6) * Math.PI * 2 + Math.PI / 6;
            var px = cx + tangent.x * Math.cos(angle) * size + bitangent.x * Math.sin(angle) * size;
            var py = cy + tangent.y * Math.cos(angle) * size + bitangent.y * Math.sin(angle) * size;
            var pz = cz + tangent.z * Math.cos(angle) * size + bitangent.z * Math.sin(angle) * size;
            pts.push(new THREE.Vector3(px, py, pz));
        }
        return pts;
    }

    var hexLatSteps  = 5;
    var hexLonSteps  = 8;
    for (var hli = -hexLatSteps; hli <= hexLatSteps; hli++) {
        var hlat = (hli / hexLatSteps) * (Math.PI / 2) * 0.8;
        for (var hlo = 0; hlo < hexLonSteps; hlo++) {
            var hlon = (hlo / hexLonSteps) * Math.PI * 2;
            var hx = HEX_R * Math.cos(hlat) * Math.cos(hlon);
            var hy = HEX_R * Math.sin(hlat);
            var hz = HEX_R * Math.cos(hlat) * Math.sin(hlon);
            var hpts = buildHexPoints(hx, hy, hz, hx, hy, hz, hexSize);
            var hgeo = new THREE.BufferGeometry().setFromPoints(hpts);
            var hmat = new THREE.LineBasicMaterial({
                color: 0xff8800,
                transparent: true,
                opacity: 0.12,
                blending: THREE.AdditiveBlending,
                depthWrite: false,
            });
            hexGroup.add(new THREE.Line(hgeo, hmat));
        }
    }
    orbGroup.add(hexGroup);

    // ── ORBITING DEBRIS & PARTICLES ──────────────────────────────────────────
    const debrisGeos = [
        new THREE.IcosahedronGeometry(0.012, 0),
        new THREE.IcosahedronGeometry(0.02,  0),
        new THREE.TetrahedronGeometry(0.015, 0),
    ];
    const debris = [];
    var debrisTrails = [];
    for (let i = 0; i < 80; i++) {
        const geo  = debrisGeos[Math.floor(Math.random() * debrisGeos.length)];
        const mat  = new THREE.MeshBasicMaterial({
            color: Math.random() > 0.6 ? 0xffaa30 : 0xdd7700,
            transparent: true, opacity: 0.4 + Math.random() * 0.5,
            blending: THREE.AdditiveBlending,
        });
        const mesh    = new THREE.Mesh(geo, mat);
        const orbitR  = 1.2 + Math.random() * 3.5;
        const speed   = (0.1 + Math.random() * 0.5) * (Math.random() > 0.5 ? 1 : -1);
        const tiltX   = (Math.random() - 0.5) * Math.PI * 0.9;
        const tiltZ   = (Math.random() - 0.5) * Math.PI * 0.5;
        const phase   = Math.random() * Math.PI * 2;
        mesh.userData = { orbitR, speed, tiltX, tiltZ, phase };
        debris.push(mesh);
        orbGroup.add(mesh);

        var trail = [];
        for (var ti = 0; ti < 3; ti++) {
            var trailMat = new THREE.MeshBasicMaterial({
                color: 0xffdd88,
                transparent: true,
                opacity: 0.15 - ti * 0.04,
                blending: THREE.AdditiveBlending,
            });
            var trailMesh = new THREE.Mesh(
                new THREE.SphereGeometry(0.005 + (2 - ti) * 0.003, 4, 4),
                trailMat
            );
            trailMesh.userData = { offsetAngle: (ti + 1) * 0.08 };
            orbGroup.add(trailMesh);
            trail.push(trailMesh);
        }
        debrisTrails.push(trail);
    }

    // ── SCANNING RINGS ───────────────────────────────────────────────────────
    function makeScanRing(radius, thickness) {
        var tk = thickness || 0.012;
        const geo = new THREE.RingGeometry(radius - tk, radius + tk, 100);
        const mat = new THREE.MeshBasicMaterial({
            color: 0xffaa30, transparent: true, opacity: 0,
            blending: THREE.AdditiveBlending, side: THREE.DoubleSide, depthWrite: false,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.rotation.x = Math.PI / 2;
        return mesh;
    }
    const scanRing1 = makeScanRing(R1, 0.01);
    const scanRing2 = makeScanRing(R1 * 0.7, 0.008);
    orbGroup.add(scanRing1, scanRing2);

    // ── DUST PARTICLES ───────────────────────────────────────────────────────
    const dustCount  = 800;
    const dustPos    = new Float32Array(dustCount * 3);
    for (let i = 0; i < dustCount; i++) {
        const rr    = 0.5 + Math.pow(Math.random(), 0.5) * 6;
        const theta = Math.random() * Math.PI * 2;
        const phi   = Math.acos(2 * Math.random() - 1);
        dustPos[i * 3]     = rr * Math.sin(phi) * Math.cos(theta);
        dustPos[i * 3 + 1] = rr * Math.cos(phi);
        dustPos[i * 3 + 2] = rr * Math.sin(phi) * Math.sin(theta);
    }
    const dustGeo = new THREE.BufferGeometry();
    dustGeo.setAttribute("position", new THREE.Float32BufferAttribute(dustPos, 3));
    const dustMat = new THREE.PointsMaterial({
        size: 0.05, color: 0xffaa30,
        transparent: true, opacity: 0.4,
        blending: THREE.AdditiveBlending, depthWrite: false, sizeAttenuation: true,
    });
    const dustPoints = new THREE.Points(dustGeo, dustMat);
    orbGroup.add(dustPoints);

    // ── GESTURE / PROGRAMMATIC CAMERA CONTROL ────────────────────────────────
    const sphericalScratch = new THREE.Spherical();
    const offsetScratch    = new THREE.Vector3();

    function rotateBy(deltaTheta, deltaPhi) {
        offsetScratch.copy(camera.position).sub(controls.target);
        sphericalScratch.setFromVector3(offsetScratch);
        sphericalScratch.theta -= deltaTheta;
        sphericalScratch.phi    = THREE.MathUtils.clamp(
            sphericalScratch.phi - deltaPhi, 0.05, Math.PI - 0.05
        );
        sphericalScratch.makeSafe();
        offsetScratch.setFromSpherical(sphericalScratch);
        camera.position.copy(controls.target).add(offsetScratch);
        camera.lookAt(controls.target);
    }
    function zoomBy(factor) {
        offsetScratch.copy(camera.position).sub(controls.target);
        const dist = THREE.MathUtils.clamp(offsetScratch.length() * factor, MIN_DISTANCE, MAX_DISTANCE);
        offsetScratch.setLength(dist);
        camera.position.copy(controls.target).add(offsetScratch);
    }
    function resetView() {
        camera.position.copy(HOME_POSITION);
        controls.target.set(0, 0, 0);
        camera.lookAt(controls.target);
        controls.update();
    }

    // ── STATE MACHINE ────────────────────────────────────────────────────────
    function setState(state) {
        const normalized = String(state || "IDLE").toUpperCase();
        aiState = normalized;
        const cfg = STATE_COLORS[normalized] || STATE_COLORS.IDLE;
        
        targetCoreColor.setHex(cfg.core);
        targetGlowColor.setHex(cfg.glow);
        targetRingColor.setHex(cfg.ring);
        targetNeuralColor.setHex(cfg.neural || cfg.core);
        targetBloom = cfg.bloom * (UI_CONFIG.reducedMotion ? 0.7 : 1.0) * UI_CONFIG.glowIntensity;

        // Auto trigger shockwave on positive one-shot transitions
        if (normalized === "SUCCESS") {
            triggerShockwave(0xffd700);
        } else if (normalized === "VERIFIED_NURI") {
            triggerShockwave(0xff6600);
        } else if (normalized === "VERIFIED_RABIA") {
            triggerShockwave(0xff3399);
        }
    }

    function setAudioEnergy(mic = 0.0, speaker = 0.0) {
        liveMicEnergy     = Math.min(1.0, Math.max(0.0, Number(mic) || 0.0));
        liveSpeakerEnergy = Math.min(1.0, Math.max(0.0, Number(speaker) || 0.0));
    }

    function setUIConfig(cfg = {}) {
        Object.assign(UI_CONFIG, cfg);
        if (UI_CONFIG.reducedMotion) {
            targetBloom = (STATE_COLORS[aiState]?.bloom || 1.4) * 0.7;
        }
    }

    // ── ANIMATION LOOP ───────────────────────────────────────────────────────
    const clock        = new THREE.Clock();
    let flickerTimer   = 0;
    let arcTimer       = 0;
    let rafId          = 0;
    let disposed       = false;
    let currentCoreScale   = 1.0;
    let currentGlowOpacity = 0.04;
    let strobeTimer        = 0;
    let debrisSpeedMult    = 1.0;
    let targetDebrisSpeedMult = 1.0;

    function animate() {
        if (disposed) return;
        rafId = requestAnimationFrame(animate);
        const delta = Math.min(clock.getDelta(), 0.1);
        const t     = clock.getElapsedTime();

        // ── Smooth Color & Bloom Interpolation
        const lerpSpeed = 0.05 * UI_CONFIG.transitionSpeed;
        currentBloom += (targetBloom - currentBloom) * lerpSpeed;
        bloom.strength = currentBloom;

        currentCoreColor.lerp(targetCoreColor, lerpSpeed);
        currentGlowColor.lerp(targetGlowColor, lerpSpeed);
        currentRingColor.lerp(targetRingColor, lerpSpeed * 1.2);
        currentNeuralColor.lerp(targetNeuralColor, lerpSpeed);

        coreSphereMat.color.copy(currentCoreColor);
        glowSphereMat.color.copy(currentGlowColor);
        icoWireMat.color.copy(currentCoreColor);
        energyRingMat.color.copy(currentRingColor);
        energyRing2Mat.color.copy(currentRingColor);
        axonMat.color.copy(currentNeuralColor);

        // ── Speed Multipliers by State
        var outerRotSpeed  = 0.0015;
        var innerRotSpeed  = 0.005;
        var icoRotXSpeed   = 0.008;
        var icoRotYSpeed   = 0.012;
        var meridianRotSpd = 0.0008;
        var sparkSpeedMult = 1.0;
        targetDebrisSpeedMult = 1.0;

        if (aiState === "IDLE") {
            outerRotSpeed  = 0.0008;
            innerRotSpeed  = 0.003;
            icoRotXSpeed   = 0.005;
            icoRotYSpeed   = 0.007;
            meridianRotSpd = 0.0004;
            sparkSpeedMult = 0.8;
        } else if (aiState === "LISTENING") {
            outerRotSpeed  = 0.0025 + liveMicEnergy * 0.004;
            innerRotSpeed  = 0.008  + liveMicEnergy * 0.010;
            icoRotXSpeed   = 0.015  + liveMicEnergy * 0.020;
            icoRotYSpeed   = 0.020  + liveMicEnergy * 0.025;
            meridianRotSpd = 0.0015;
            sparkSpeedMult = 1.8 + liveMicEnergy * 2.0;
        } else if (aiState === "SPEAKING") {
            outerRotSpeed  = 0.0035 + liveSpeakerEnergy * 0.005;
            innerRotSpeed  = 0.014  + liveSpeakerEnergy * 0.015;
            icoRotXSpeed   = 0.028  + liveSpeakerEnergy * 0.030;
            icoRotYSpeed   = 0.035  + liveSpeakerEnergy * 0.040;
            meridianRotSpd = 0.0025;
            targetDebrisSpeedMult = 2.5 + liveSpeakerEnergy * 2.0;
            sparkSpeedMult = 2.4 + liveSpeakerEnergy * 2.0;
        } else if (aiState === "THINKING") {
            outerRotSpeed  = 0.003;
            innerRotSpeed  = 0.012;
            icoRotXSpeed   = 0.032;
            icoRotYSpeed   = 0.040;
            meridianRotSpd = 0.0018;
            sparkSpeedMult = 3.8;
        } else if (aiState === "EXECUTING") {
            outerRotSpeed  = 0.0045;
            innerRotSpeed  = 0.018;
            icoRotXSpeed   = 0.040;
            icoRotYSpeed   = 0.055;
            meridianRotSpd = 0.0035;
            targetDebrisSpeedMult = 3.2;
            sparkSpeedMult = 4.2;
        } else if (aiState === "OBSERVING") {
            outerRotSpeed  = 0.0012;
            innerRotSpeed  = 0.006;
            icoRotXSpeed   = 0.010;
            icoRotYSpeed   = 0.014;
            meridianRotSpd = 0.0010;
            sparkSpeedMult = 1.4;
        } else if (aiState === "CONFIRMING") {
            outerRotSpeed  = 0.0006;
            innerRotSpeed  = 0.002;
            icoRotXSpeed   = 0.004;
            icoRotYSpeed   = 0.006;
            meridianRotSpd = 0.0003;
            sparkSpeedMult = 0.5;
        } else if (aiState === "UNKNOWN_SPEAKER") {
            outerRotSpeed  = 0.001;
            innerRotSpeed  = 0.003;
            icoRotXSpeed   = 0.006;
            icoRotYSpeed   = 0.008;
            sparkSpeedMult = 0.6;
        } else if (aiState === "ERROR") {
            outerRotSpeed  = 0.001;
            innerRotSpeed  = 0.004;
            icoRotXSpeed   = 0.008;
            icoRotYSpeed   = 0.010;
            meridianRotSpd = 0.0005;
            sparkSpeedMult = 0.5;
        } else if (aiState === "DISCONNECTED") {
            outerRotSpeed  = 0.0003;
            innerRotSpeed  = 0.001;
            icoRotXSpeed   = 0.002;
            icoRotYSpeed   = 0.003;
            meridianRotSpd = 0.0001;
            sparkSpeedMult = 0.2;
        }

        if (UI_CONFIG.reducedMotion) {
            outerRotSpeed  *= 0.3;
            innerRotSpeed  *= 0.3;
            icoRotXSpeed   *= 0.3;
            icoRotYSpeed   *= 0.3;
            meridianRotSpd *= 0.3;
            sparkSpeedMult *= 0.4;
            targetDebrisSpeedMult = 0.5;
        }

        debrisSpeedMult += (targetDebrisSpeedMult - debrisSpeedMult) * 0.04;

        // ── Rotations
        outerShell.rotation.y += outerRotSpeed;
        outerShell.rotation.x  = Math.sin(t * 0.08) * 0.05;
        shell2.rotation.y     -= 0.001;
        shell2.rotation.z      = Math.sin(t * 0.12) * 0.03;
        innerCore.rotation.y  -= innerRotSpeed;
        innerCore.rotation.z  += innerRotSpeed * 0.4;
        innerCore.rotation.x   = Math.cos(t * 0.1) * 0.08;
        icoWire.rotation.x    += icoRotXSpeed;
        icoWire.rotation.y    += icoRotYSpeed;

        neuralGroup.rotation.y += outerRotSpeed * 0.6;
        neuralGroup.rotation.x = Math.sin(t * 0.05) * 0.03;

        meridianGroup.rotation.y += meridianRotSpd;
        hexGroup.rotation.y -= 0.0003;

        // ── Dynamic Optical Reticle Animation (OBSERVING)
        if (aiState === "OBSERVING") {
            reticleMat.opacity = Math.min(0.85, reticleMat.opacity + 0.04);
            reticleMat.color.copy(currentRingColor);
            reticleRing.rotation.z += 0.015;
            bracketLines.rotation.z -= 0.008;
        } else {
            reticleMat.opacity = Math.max(0.0, reticleMat.opacity - 0.05);
        }

        // ── Dynamic Directional Plasma Flux (EXECUTING)
        if (aiState === "EXECUTING") {
            plasmaDots.forEach(p => {
                p.theta += p.speed * delta;
                const px = p.radius * Math.cos(p.theta);
                const py = p.altitude + Math.sin(p.theta * 2 + t * 4) * 0.15;
                const pz = p.radius * Math.sin(p.theta);
                p.mesh.position.set(px, py, pz);
                p.mesh.material.color.copy(currentCoreColor);
                p.mesh.material.opacity = 0.85;
            });
        } else {
            plasmaDots.forEach(p => {
                p.mesh.material.opacity = Math.max(0.0, p.mesh.material.opacity - 0.05);
            });
        }

        // ── Dynamic Shockwave Flare Animation (SUCCESS/VERIFIED)
        if (shockwaveActive) {
            shockwaveProgress += delta * 1.35;
            if (shockwaveProgress >= 1.0) {
                shockwaveActive = false;
                shockwaveMat.opacity = 0.0;
            } else {
                const scale = 0.4 + shockwaveProgress * 3.8;
                shockwaveRing.scale.set(scale, scale, scale);
                shockwaveMat.color.copy(shockwaveColor);
                shockwaveMat.opacity = (1.0 - shockwaveProgress) * 0.9;
            }
        }

        // ── Neural Network Synaptic Simulation
        const axonPosAttr = axonGeo.attributes.position;
        let pIndex = 0;

        for (let ni = 0; ni < neuralNodes.length; ni++) {
            const node = neuralNodes[ni];
            let pulseFreq = (aiState === "THINKING") ? 14 : (aiState === "EXECUTING") ? 16 : (aiState === "SPEAKING") ? 8 : (aiState === "LISTENING") ? 5 : 2;
            let pulse = Math.sin(t * pulseFreq * node.speed + node.phase);
            
            let jitter = (aiState === "THINKING" || aiState === "EXECUTING") ? (Math.random() - 0.5) * 0.025 : 0;
            node.pos.x = node.basePos.x + Math.sin(t * 0.8 + node.phase) * 0.03 + jitter;
            node.pos.y = node.basePos.y + Math.cos(t * 0.7 + node.phase) * 0.03 + jitter;
            node.pos.z = node.basePos.z + Math.sin(t * 0.9 + node.phase) * 0.03 + jitter;
            node.mesh.position.copy(node.pos);

            let nodeScale = 1.0 + Math.max(0, pulse * 0.8);
            if (aiState === "THINKING" || aiState === "EXECUTING") nodeScale += Math.random() * 0.6;
            node.mesh.scale.setScalar(nodeScale);
            node.mesh.material.color.copy(currentNeuralColor);
            node.mesh.material.opacity = (aiState === "THINKING" || aiState === "EXECUTING") ? (0.6 + Math.random() * 0.4) : (0.4 + pulse * 0.3);
        }

        for (let ap = 0; ap < axonPairs.length; ap++) {
            const nA = neuralNodes[axonPairs[ap][0]];
            const nB = neuralNodes[axonPairs[ap][1]];
            axonPosAttr.array[pIndex++] = nA.pos.x;
            axonPosAttr.array[pIndex++] = nA.pos.y;
            axonPosAttr.array[pIndex++] = nA.pos.z;
            axonPosAttr.array[pIndex++] = nB.pos.x;
            axonPosAttr.array[pIndex++] = nB.pos.y;
            axonPosAttr.array[pIndex++] = nB.pos.z;
        }
        axonPosAttr.needsUpdate = true;
        axonMat.opacity = (aiState === "THINKING" || aiState === "EXECUTING") ? (0.45 + Math.sin(t * 12) * 0.25) : (aiState === "SPEAKING") ? 0.35 : 0.2;

        // Action Potential Sparks Moving along Axons
        for (let si = 0; si < neuralSparks.length; si++) {
            const sp = neuralSparks[si];
            sp.progress += sp.speed * sparkSpeedMult;
            if (sp.progress >= 1.0) {
                sp.progress = 0;
                const curTarget = neuralNodes[sp.toNode];
                if (curTarget && curTarget.connections.length > 0) {
                    sp.fromNode = sp.toNode;
                    sp.toNode   = curTarget.connections[Math.floor(Math.random() * curTarget.connections.length)];
                } else {
                    const newPair = axonPairs[Math.floor(Math.random() * axonPairs.length)] || [0, 1];
                    sp.fromNode = newPair[0];
                    sp.toNode   = newPair[1];
                }
            }
            const pA = neuralNodes[sp.fromNode]?.pos || neuralNodes[0].pos;
            const pB = neuralNodes[sp.toNode]?.pos   || neuralNodes[1].pos;
            sp.mesh.position.lerpVectors(pA, pB, sp.progress);
            sp.mesh.material.color.copy(currentNeuralColor);
            sp.mesh.scale.setScalar((aiState === "THINKING" || aiState === "EXECUTING") ? (1.5 + Math.random() * 0.8) : 1.0);
        }

        // Synaptic Neural Electric Arc Discharges
        arcTimer += delta;
        if (aiState === "THINKING" || aiState === "EXECUTING" || (aiState === "SPEAKING" && Math.random() > 0.7)) {
            arcMat.opacity = 0.85;
            arcMat.color.copy(currentNeuralColor);
            const arcArr = arcGeo.attributes.position.array;
            let arcIdx = 0;
            for (let ai = 0; ai < ARC_COUNT; ai++) {
                const targetNode = neuralNodes[Math.floor(Math.random() * neuralNodes.length)];
                let curP = new THREE.Vector3(0, 0, 0);
                let endP = targetNode.pos;
                for (let seg = 0; seg < 7; seg++) {
                    let nextP = new THREE.Vector3().lerpVectors(curP, endP, (seg + 1) / 7);
                    nextP.x += (Math.random() - 0.5) * 0.12;
                    nextP.y += (Math.random() - 0.5) * 0.12;
                    nextP.z += (Math.random() - 0.5) * 0.12;

                    arcArr[arcIdx++] = curP.x;
                    arcArr[arcIdx++] = curP.y;
                    arcArr[arcIdx++] = curP.z;
                    arcArr[arcIdx++] = nextP.x;
                    arcArr[arcIdx++] = nextP.y;
                    arcArr[arcIdx++] = nextP.z;
                    curP = nextP;
                }
            }
            arcGeo.attributes.position.needsUpdate = true;
        } else {
            arcMat.opacity *= 0.85;
        }

        // ── Core pulse & waveforms
        const wave1 = Math.sin(t * 1.2);
        const wave3 = Math.pow(Math.max(0, Math.sin(t * 0.4)), 5);
        const wave4 = Math.pow(Math.max(0, Math.sin(t * 0.7 + 2)), 8);
        const surge = wave3 * 1.5 + wave4 * 2.0;

        let targetCoreScaleVal   = 1.0;
        let targetGlowOpacityVal = 0.04;
        var ringPulse            = 0.55;
        var ringPulse2           = 0.30;

        if (aiState === "IDLE") {
            targetCoreScaleVal   = 1.0 + Math.sin(t * 0.8) * 0.02;
            targetGlowOpacityVal = 0.04;
            ringPulse            = 0.3 + Math.sin(t * 0.8) * 0.1;
            ringPulse2           = 0.15 + Math.sin(t * 0.8 + 1) * 0.05;
        } else if (aiState === "LISTENING") {
            targetCoreScaleVal   = 1.2 + Math.sin(t * 2) * 0.05 + liveMicEnergy * 0.25;
            targetGlowOpacityVal = 0.15 + liveMicEnergy * 0.20;
            ringPulse            = 0.6 + Math.sin(t * 3) * 0.25 + liveMicEnergy * 0.35;
            ringPulse2           = 0.35 + Math.sin(t * 3.5) * 0.15 + liveMicEnergy * 0.25;
        } else if (aiState === "THINKING") {
            const brainwave = Math.sin(t * 12) * 0.15 + Math.sin(t * 24) * 0.08;
            targetCoreScaleVal   = 1.15 + brainwave;
            targetGlowOpacityVal = 0.18 + Math.random() * 0.08;
            ringPulse            = 0.5 + Math.sin(t * 6) * 0.3 + (Math.random() > 0.8 ? 0.3 : 0);
            ringPulse2           = 0.3 + Math.sin(t * 8) * 0.2;
        } else if (aiState === "EXECUTING") {
            const powerPulse = Math.sin(t * 16) * 0.18 + Math.cos(t * 8) * 0.08;
            targetCoreScaleVal   = 1.25 + powerPulse;
            targetGlowOpacityVal = 0.24 + Math.random() * 0.06;
            ringPulse            = 0.75 + Math.sin(t * 10) * 0.25;
            ringPulse2           = 0.50 + Math.sin(t * 12) * 0.20;
        } else if (aiState === "OBSERVING") {
            targetCoreScaleVal   = 1.08 + Math.sin(t * 1.5) * 0.04;
            targetGlowOpacityVal = 0.12;
            ringPulse            = 0.5 + Math.sin(t * 2) * 0.15;
            ringPulse2           = 0.25 + Math.cos(t * 2) * 0.10;
        } else if (aiState === "SPEAKING") {
            targetCoreScaleVal   = 1.2 + Math.random() * 0.1 + liveSpeakerEnergy * 0.35;
            targetGlowOpacityVal = 0.20 + Math.random() * 0.05 + liveSpeakerEnergy * 0.25;
            ringPulse            = 0.7 + Math.random() * 0.3 + liveSpeakerEnergy * 0.30;
            ringPulse2           = 0.4 + Math.random() * 0.2 + liveSpeakerEnergy * 0.20;
        } else if (aiState === "CONFIRMING") {
            const holdPulse = Math.sin(t * 3.5) * 0.12;
            targetCoreScaleVal   = 1.10 + holdPulse;
            targetGlowOpacityVal = 0.16 + holdPulse * 0.5;
            ringPulse            = 0.65 + holdPulse * 0.4;
            ringPulse2           = 0.35 + holdPulse * 0.3;
        } else if (aiState === "WARNING") {
            const warnPulse = Math.sin(t * 5.0) * 0.18;
            targetCoreScaleVal   = 1.15 + Math.max(0, warnPulse);
            targetGlowOpacityVal = 0.20 + Math.max(0, warnPulse * 0.6);
            ringPulse            = 0.7 + Math.max(0, warnPulse * 0.5);
            ringPulse2           = 0.4 + Math.max(0, warnPulse * 0.4);
        } else if (aiState === "ERROR") {
            strobeTimer += delta;
            var strobeOn = Math.sin(strobeTimer * 12) > 0;
            targetCoreScaleVal   = strobeOn ? 1.2 : 0.95;
            targetGlowOpacityVal = strobeOn ? 0.35 : 0.08;
            ringPulse            = strobeOn ? 0.85 : 0.2;
            ringPulse2           = strobeOn ? 0.45 : 0.1;
        } else if (aiState === "DISCONNECTED") {
            targetCoreScaleVal   = 0.85 + Math.sin(t * 0.4) * 0.02;
            targetGlowOpacityVal = 0.02;
            ringPulse            = 0.15;
            ringPulse2           = 0.05;
        }

        currentCoreScale   += (targetCoreScaleVal   - currentCoreScale)   * 0.05;
        currentGlowOpacity += (targetGlowOpacityVal - currentGlowOpacity) * 0.05;

        const coreScale  = currentCoreScale + surge + Math.sin(t * 5) * 0.05;
        coreSphere.scale.setScalar(coreScale);
        coreSphereMat.opacity = Math.min(0.6, Math.max(0, 0.08 + wave1 * 0.05 + surge * 0.2));
        glowSphere.scale.setScalar(currentCoreScale + surge * 0.8);
        glowSphereMat.opacity = Math.max(0, currentGlowOpacity + surge * 0.08);
        icoWire.scale.setScalar(1 + surge * 0.6);
        icoWireMat.opacity = Math.min(1, 0.5 + surge * 0.4);

        // ── Energy ring pulsing
        energyRingMat.opacity  = Math.max(0, Math.min(1, ringPulse));
        energyRing2Mat.opacity = Math.max(0, Math.min(1, ringPulse2));
        energyRing.scale.setScalar(1 + surge * 0.05 + Math.sin(t * 2) * 0.01);
        energyRing2.scale.setScalar(1 + surge * 0.04 + Math.sin(t * 2.5 + 1) * 0.01);

        // ── Energy field opacity
        energyFieldMat.color.copy(currentRingColor);
        energyFieldMat.opacity = 0.02 + surge * 0.015 + Math.sin(t * 0.6) * 0.008;

        // ── Meridian beam glow
        var mOpacity = 0.85;
        if (aiState === "IDLE")         mOpacity = 0.4 + Math.sin(t * 0.6) * 0.15;
        if (aiState === "LISTENING")    mOpacity = 0.9 + Math.sin(t * 3) * 0.1;
        if (aiState === "SPEAKING")     mOpacity = 0.95 + Math.random() * 0.05;
        if (aiState === "THINKING")     mOpacity = 0.75 + Math.sin(t * 8) * 0.25;
        if (aiState === "EXECUTING")    mOpacity = 0.90 + Math.sin(t * 10) * 0.10;
        if (aiState === "ERROR")        mOpacity = energyRingMat.opacity;
        if (aiState === "DISCONNECTED") mOpacity = 0.2;

        for (var mii = 0; mii < meridianLines.length; mii++) {
            meridianLines[mii].mat.color.copy(currentRingColor);
            meridianLines[mii].mat.opacity = mOpacity;
        }

        // ── Debris + trails
        debris.forEach((d, idx) => {
            const u  = d.userData;
            const a  = t * u.speed * debrisSpeedMult + u.phase;
            const px = u.orbitR * Math.cos(a) * Math.cos(u.tiltX);
            const py = u.orbitR * Math.sin(u.tiltX) * Math.sin(a * 0.8) + Math.sin(a * 0.3 + u.tiltZ) * 0.2;
            const pz = u.orbitR * Math.sin(a) * Math.cos(u.tiltZ);
            d.position.set(px, py, pz);
            d.rotation.x += 0.015;
            d.rotation.z += 0.01;

            var trail = debrisTrails[idx];
            if (trail) {
                for (var ti2 = 0; ti2 < trail.length; ti2++) {
                    var trailDot = trail[ti2];
                    var tOffset  = trailDot.userData.offsetAngle * (u.speed >= 0 ? -1 : 1);
                    var ta = t * u.speed * debrisSpeedMult + u.phase + tOffset;
                    trailDot.position.set(
                        u.orbitR * Math.cos(ta) * Math.cos(u.tiltX),
                        u.orbitR * Math.sin(u.tiltX) * Math.sin(ta * 0.8) + Math.sin(ta * 0.3 + u.tiltZ) * 0.2,
                        u.orbitR * Math.sin(ta) * Math.cos(u.tiltZ)
                    );
                    var baseOp = (0.15 - ti2 * 0.04) * debrisSpeedMult * 0.5;
                    trailDot.material.opacity = Math.min(0.5, Math.max(0, baseOp));
                }
            }
        });

        // ── Scan rings
        var scanOpBase1 = 0.2;
        var scanOpBase2 = 0.15;
        if (aiState === "LISTENING") { scanOpBase1 = 0.5; scanOpBase2 = 0.4; }
        if (aiState === "SPEAKING")  { scanOpBase1 = 0.6; scanOpBase2 = 0.5; }
        if (aiState === "THINKING" || aiState === "EXECUTING") { scanOpBase1 = 0.45; scanOpBase2 = 0.38; }

        const scanY1 = Math.sin(t * 0.4) * R1;
        scanRing1.position.y = scanY1;
        const scanS1 = Math.sqrt(Math.max(0, R1 * R1 - scanY1 * scanY1)) / R1;
        scanRing1.scale.set(scanS1, scanS1, 1);
        scanRing1.material.opacity = scanOpBase1 * scanS1;
        scanRing1.material.color.copy(currentRingColor);

        const scanY2 = Math.sin(t * 0.6 + 2) * R3;
        scanRing2.position.y = scanY2;
        const scanS2 = Math.sqrt(Math.max(0, R3 * R3 - scanY2 * scanY2)) / R3;
        scanRing2.scale.set(scanS2, scanS2, 1);
        scanRing2.material.opacity = scanOpBase2 * scanS2;
        scanRing2.material.color.copy(currentRingColor);

        // ── Dust
        dustPoints.rotation.y += 0.0002;
        dustMat.color.copy(currentCoreColor);

        // ── Hex grid opacity
        var hexOp = 0.1 + Math.sin(t * 0.5) * 0.04;
        if (aiState === "SPEAKING") hexOp = 0.18 + Math.random() * 0.08;
        if (aiState === "THINKING" || aiState === "EXECUTING") hexOp = 0.22 + Math.random() * 0.06;
        hexGroup.children.forEach(function(child) {
            if (child.material) child.material.opacity = Math.max(0, hexOp);
        });

        flickerTimer += delta;

        // ── Satellite Agent Sub-Orbs Animation
        for (const [agentId, orbObj] of activeAgentOrbs.entries()) {
            orbObj.currentScale += (orbObj.targetScale - orbObj.currentScale) * 0.12;
            orbObj.group.scale.setScalar(Math.max(0.001, orbObj.currentScale));

            if (orbObj.dead && orbObj.currentScale < 0.01) {
                agentOrbsGroup.remove(orbObj.group);
                agentOrbsGroup.remove(orbObj.beamLine);
                orbObj.trailDots.forEach(td => agentOrbsGroup.remove(td.mesh));
                activeAgentOrbs.delete(agentId);
                continue;
            }

            const u = orbObj.cfg;
            const a = t * u.speed + orbObj.phase;
            const px = u.radius * Math.cos(a) * Math.cos(u.tiltX);
            const py = u.radius * Math.sin(u.tiltX) * Math.sin(a * 0.8) + Math.sin(t * 3 + orbObj.phase) * 0.25;
            const pz = u.radius * Math.sin(a) * Math.cos(u.tiltZ);

            orbObj.group.position.set(px, py, pz);
            orbObj.group.rotation.y += 0.03;
            orbObj.group.rotation.x += 0.02;
            orbObj.ring1.rotation.z += 0.05;
            orbObj.ring2.rotation.x += 0.04;
            orbObj.ring2.rotation.y += 0.03;

            const pulse = 1.0 + Math.sin(t * 8 + orbObj.phase) * 0.15;
            orbObj.core.scale.setScalar(pulse);
            orbObj.halo.scale.setScalar(pulse * 1.1);

            const posArr = orbObj.beamGeo.attributes.position.array;
            posArr[0] = 0; posArr[1] = 0; posArr[2] = 0;
            posArr[3] = px; posArr[4] = py; posArr[5] = pz;
            orbObj.beamGeo.attributes.position.needsUpdate = true;
            orbObj.beamLine.material.opacity = (0.25 + Math.sin(t * 6 + orbObj.phase) * 0.18) * orbObj.currentScale;

            orbObj.trailDots.forEach(td => {
                const ta = a - td.offset * (u.speed >= 0 ? 1 : -1);
                const tx = u.radius * Math.cos(ta) * Math.cos(u.tiltX);
                const ty = u.radius * Math.sin(u.tiltX) * Math.sin(ta * 0.8) + Math.sin(t * 3 + orbObj.phase) * 0.25;
                const tz = u.radius * Math.sin(ta) * Math.cos(u.tiltZ);
                td.mesh.position.set(tx, ty, tz);
                td.mesh.scale.setScalar(orbObj.currentScale);
            });
        }

        controls.update();
        composer.render();
    }

    // ═══════════════════════════════════════════════════════════════════════════
    // LAYER 7: SATELLITE AGENT SUB-ORBS (Multi-Agent Orbital Network)
    // ═══════════════════════════════════════════════════════════════════════════
    const agentOrbsGroup = new THREE.Group();
    orbGroup.add(agentOrbsGroup);

    const AGENT_THEMES = {
        coding_agent:    { name: "Coding Agent",   icon: "💻", color: 0x00e5ff, glow: 0x0088ff, radius: 3.1, size: 0.36, speed: 1.1,  tiltX: 0.35,  tiltZ: 0.25 },
        testing_agent:   { name: "Testing Agent",  icon: "🧪", color: 0x00ff88, glow: 0x00cc44, radius: 3.6, size: 0.32, speed: -0.9, tiltX: -0.45, tiltZ: 0.45 },
        reviewer_agent:  { name: "Reviewer Agent", icon: "🧐", color: 0xffaa00, glow: 0xff6600, radius: 4.0, size: 0.34, speed: 0.8,  tiltX: 0.60,  tiltZ: -0.35 },
        research_agent:  { name: "Research Agent", icon: "🧠", color: 0xd900ff, glow: 0x8800ff, radius: 4.4, size: 0.35, speed: -1.0, tiltX: -0.55, tiltZ: -0.40 },
        terminal_agent:  { name: "Terminal Agent", icon: "⚡", color: 0xff3300, glow: 0xcc1100, radius: 3.3, size: 0.30, speed: 1.3,  tiltX: 0.20,  tiltZ: -0.60 },
        computer_agent:  { name: "Computer Agent", icon: "👁️", color: 0x00ffcc, glow: 0x00aaff, radius: 3.8, size: 0.33, speed: -0.8, tiltX: 0.45,  tiltZ: 0.30 },
        supervisor:      { name: "Supervisor",     icon: "👑", color: 0xff0077, glow: 0xaa0033, radius: 4.8, size: 0.42, speed: 0.6,  tiltX: 0.15,  tiltZ: 0.15 },
    };

    const activeAgentOrbs = new Map();

    function createAgentOrbMesh(cfg) {
        const group = new THREE.Group();

        const coreMat = new THREE.MeshBasicMaterial({
            color: cfg.color,
            transparent: true,
            opacity: 0.95,
            blending: THREE.AdditiveBlending,
        });
        const core = new THREE.Mesh(new THREE.SphereGeometry(cfg.size * 0.45, 16, 16), coreMat);
        group.add(core);

        const icoGeo = new THREE.IcosahedronGeometry(cfg.size * 0.75, 1);
        const icoMat = lineMat(cfg.color, 0.85);
        const icoWire = new THREE.LineSegments(new THREE.EdgesGeometry(icoGeo), icoMat);
        group.add(icoWire);

        const ringGeo1 = latRing(cfg.size * 1.05, 0, 48);
        const ringMat1 = lineMat(cfg.glow, 0.75);
        const ring1 = new THREE.Line(ringGeo1, ringMat1);
        ring1.rotation.x = Math.PI / 3;
        group.add(ring1);

        const ringGeo2 = latRing(cfg.size * 1.15, 0, 48);
        const ringMat2 = lineMat(cfg.color, 0.60);
        const ring2 = new THREE.Line(ringGeo2, ringMat2);
        ring2.rotation.y = Math.PI / 3;
        ring2.rotation.z = Math.PI / 4;
        group.add(ring2);

        const haloMat = new THREE.MeshBasicMaterial({
            color: cfg.glow,
            transparent: true,
            opacity: 0.16,
            blending: THREE.AdditiveBlending,
            depthWrite: false,
        });
        const halo = new THREE.Mesh(new THREE.SphereGeometry(cfg.size * 1.35, 16, 16), haloMat);
        group.add(halo);

        const beamPts = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 0, 0)];
        const beamGeo = new THREE.BufferGeometry().setFromPoints(beamPts);
        const beamMat = lineMat(cfg.color, 0.35);
        const beamLine = new THREE.Line(beamGeo, beamMat);
        agentOrbsGroup.add(beamLine);

        const trailDots = [];
        for (let ti = 0; ti < 4; ti++) {
            const dotMat = new THREE.MeshBasicMaterial({
                color: cfg.color,
                transparent: true,
                opacity: 0.35 - ti * 0.07,
                blending: THREE.AdditiveBlending,
            });
            const dot = new THREE.Mesh(new THREE.SphereGeometry(0.04 - ti * 0.006, 6, 6), dotMat);
            agentOrbsGroup.add(dot);
            trailDots.push({ mesh: dot, offset: (ti + 1) * 0.08 });
        }

        group.scale.set(0.001, 0.001, 0.001);

        return {
            group,
            core,
            icoWire,
            ring1,
            ring2,
            halo,
            beamLine,
            beamGeo,
            trailDots,
            cfg,
            targetScale: 1.0,
            currentScale: 0.001,
            phase: Math.random() * Math.PI * 2,
            dead: false,
        };
    }

    function spawnAgentOrb(agentId, label = "") {
        const themeKey = String(agentId || "supervisor").toLowerCase().replace(/[^a-z0-9_]/g, "");
        const cfg = AGENT_THEMES[themeKey] || {
            name: label || agentId,
            icon: "🤖",
            color: 0x00ffff,
            glow: 0x0088cc,
            radius: 3.5 + Math.random() * 0.8,
            size: 0.32,
            speed: (Math.random() > 0.5 ? 1 : -1) * (0.8 + Math.random() * 0.4),
            tiltX: (Math.random() - 0.5) * 1.2,
            tiltZ: (Math.random() - 0.5) * 1.2,
        };

        if (activeAgentOrbs.has(agentId)) {
            const existing = activeAgentOrbs.get(agentId);
            existing.targetScale = 1.0;
            existing.dead = false;
            return;
        }

        const orbObj = createAgentOrbMesh(cfg);
        agentOrbsGroup.add(orbObj.group);
        activeAgentOrbs.set(agentId, orbObj);
    }

    function removeAgentOrb(agentId) {
        if (!activeAgentOrbs.has(agentId)) return;
        const orbObj = activeAgentOrbs.get(agentId);
        orbObj.targetScale = 0.0;
        orbObj.dead = true;
    }

    function clearAgentOrbs() {
        for (const [id] of activeAgentOrbs) {
            removeAgentOrb(id);
        }
    }

    animate();

    // ── RESIZE ────────────────────────────────────────────────────────────────
    function onResize() {
        const w = container.clientWidth  || window.innerWidth;
        const h = container.clientHeight || window.innerHeight;
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
        renderer.setSize(w, h);
        composer.setSize(w, h);
    }
    window.addEventListener("resize", onResize);

    // ── CLEANUP ───────────────────────────────────────────────────────────────
    function dispose() {
        disposed = true;
        cancelAnimationFrame(rafId);
        window.removeEventListener("resize", onResize);
        controls.dispose();
        scene.traverse((obj) => {
            if (obj.geometry) obj.geometry.dispose();
            const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
            for (const mat of mats) {
                if (mat) { if (mat.map) mat.map.dispose(); mat.dispose(); }
            }
        });
        composer.dispose();
        renderer.dispose();
        renderer.domElement.remove();
    }

    // ── 3D HOLOGRAPHIC NEURAL GRAPH & STREAM PULSES ────────────────────────
    const dynamicGraphGroup = new THREE.Group();
    scene.add(dynamicGraphGroup);
    const dynamicGraphNodes = new Map();
    let dynamicGraphLines = null;

    function setNeuralDataGraph(nodes = [], edges = []) {
        // Clear previous dynamic graph meshes
        while (dynamicGraphGroup.children.length > 0) {
            const obj = dynamicGraphGroup.children[0];
            if (obj.geometry) obj.geometry.dispose();
            if (obj.material) obj.material.dispose();
            dynamicGraphGroup.remove(obj);
        }
        dynamicGraphNodes.clear();

        if (!nodes || nodes.length === 0) return;

        const nodeGeo = new THREE.SphereGeometry(0.06, 12, 12);
        const linePoints = [];

        nodes.forEach((n, idx) => {
            const col = n.status === "COMPLETED" ? 0x00ff88 : (n.status === "FAILED" ? 0xff2244 : 0x00ccff);
            const mat = new THREE.MeshBasicMaterial({
                color: col,
                transparent: true,
                opacity: 0.85,
                blending: THREE.AdditiveBlending
            });
            const mesh = new THREE.Mesh(nodeGeo, mat);
            const radius = 2.4 + (idx % 3) * 0.4;
            const theta = (idx / nodes.length) * Math.PI * 2;
            const yOffset = ((idx % 2 === 0 ? 1 : -1) * (0.3 + (idx % 4) * 0.2));
            
            mesh.position.set(radius * Math.cos(theta), yOffset, radius * Math.sin(theta));
            dynamicGraphGroup.add(mesh);
            dynamicGraphNodes.set(n.id || String(idx), mesh);
        });

        edges.forEach(e => {
            const m1 = dynamicGraphNodes.get(e.from);
            const m2 = dynamicGraphNodes.get(e.to);
            if (m1 && m2) {
                linePoints.push(m1.position.x, m1.position.y, m1.position.z);
                linePoints.push(m2.position.x, m2.position.y, m2.position.z);
            }
        });

        if (linePoints.length > 0) {
            const lineGeo = new THREE.BufferGeometry();
            lineGeo.setAttribute("position", new THREE.Float32BufferAttribute(new Float32Array(linePoints), 3));
            const lineMat = new THREE.LineBasicMaterial({
                color: 0x00eeff,
                transparent: true,
                opacity: 0.45,
                blending: THREE.AdditiveBlending
            });
            dynamicGraphLines = new THREE.LineSegments(lineGeo, lineMat);
            dynamicGraphGroup.add(dynamicGraphLines);
        }
    }

    function pulseAgentStream(agentId, intensity = 1.0) {
        if (!activeAgentOrbs.has(agentId)) return;
        const orbObj = activeAgentOrbs.get(agentId);
        orbObj.beamLine.material.opacity = Math.min(1.0, 0.9 * intensity);
        triggerShockwave(1.2 * intensity);
    }

    function triggerHoloScan() {
        triggerShockwave(1.8);
    }

    return {
        rotateBy,
        zoomBy,
        zoomIn: () => zoomBy(0.65),
        zoomOut: () => zoomBy(1.55),
        resetView,
        dispose,
        setState,
        getState: () => aiState,
        triggerShockwave,
        setAudioEnergy,
        setUIConfig,
        spawnAgentOrb,
        removeAgentOrb,
        clearAgentOrbs,
        getActiveAgentOrbs: () => Array.from(activeAgentOrbs.keys()),
        setNeuralDataGraph,
        pulseAgentStream,
        triggerHoloScan
    };
}

