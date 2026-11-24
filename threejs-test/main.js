import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";

const viewport = document.querySelector("#viewport");
const status = document.querySelector("#status");
const info = document.querySelector("#model-info");

const scene = new THREE.Scene();
scene.background = new THREE.Color("#20271f");

const camera = new THREE.PerspectiveCamera(35, 1, 0.01, 100);
camera.position.set(2.4, 1.65, 3.8);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.05;
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
viewport.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(0, 0.9, 0);
controls.minDistance = 0.7;
controls.maxDistance = 9;

scene.add(new THREE.HemisphereLight(0xe7eadb, 0x343b2e, 2.0));
const key = new THREE.DirectionalLight(0xffe4c2, 3.0);
key.position.set(3, 5, 4);
key.castShadow = true;
key.shadow.mapSize.set(1024, 1024);
scene.add(key);
const fill = new THREE.DirectionalLight(0xc8d7e8, 1.1);
fill.position.set(-4, 2, -3);
scene.add(fill);

const ground = new THREE.Mesh(
  new THREE.PlaneGeometry(30, 30),
  new THREE.MeshStandardMaterial({ color: "#555b4b", roughness: 0.92 })
);
ground.rotation.x = -Math.PI / 2;
ground.position.y = -0.012;
ground.receiveShadow = true;
scene.add(ground);

const grid = new THREE.GridHelper(10, 20, 0x879078, 0x4b5345);
grid.position.y = -0.008;
scene.add(grid);

let character = null;
let originalMaterials = [];
let wireframeOn = false;

function fitCamera(object) {
  const bounds = new THREE.Box3().setFromObject(object);
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  object.position.x -= center.x;
  object.position.z -= center.z;
  object.position.y -= bounds.min.y;
  const height = Math.max(size.y, 1);
  controls.target.set(0, height * 0.52, 0);
  camera.position.set(height * 1.35, height * 0.92, height * 2.15);
  camera.near = Math.max(0.01, height / 200);
  camera.far = height * 30;
  camera.updateProjectionMatrix();
  controls.update();
  return { height, size };
}

const loader = new GLTFLoader();
loader.load(
  "../exports/humanoid_v10.glb",
  (gltf) => {
    character = gltf.scene;
    character.traverse((node) => {
      if (!node.isMesh) return;
      node.castShadow = true;
      node.receiveShadow = true;
      originalMaterials.push({ mesh: node, material: node.material });
    });
    scene.add(character);
    const dimensions = fitCamera(character);
    const meshes = originalMaterials.length;
    status.textContent = "Model loaded. Inspect the silhouette, face, clothing and material separation.";
    info.textContent = `${meshes} mesh objects · ${dimensions.height.toFixed(2)} m tall`;
  },
  (event) => {
    if (event.total) status.textContent = `Loading model… ${Math.round(event.loaded / event.total * 100)}%`;
  },
  (error) => {
    console.error(error);
    status.classList.add("error");
    status.textContent = "Could not load ../exports/humanoid_v10.glb. Run the Blender export first, then reload this page through a local web server.";
    info.textContent = "GLB not found";
  }
);

document.querySelector("#reset-view").addEventListener("click", () => {
  if (character) fitCamera(character);
});
document.querySelector("#wireframe").addEventListener("click", (event) => {
  wireframeOn = !wireframeOn;
  event.currentTarget.setAttribute("aria-pressed", String(wireframeOn));
  for (const entry of originalMaterials) {
    const mats = Array.isArray(entry.material) ? entry.material : [entry.material];
    for (const material of mats) material.wireframe = wireframeOn;
  }
});

function resize() {
  const width = viewport.clientWidth;
  const height = viewport.clientHeight;
  camera.aspect = width / height;
  camera.updateProjectionMatrix();
  renderer.setSize(width, height, false);
}
new ResizeObserver(resize).observe(viewport);
resize();

renderer.setAnimationLoop(() => {
  controls.update();
  renderer.render(scene, camera);
});
