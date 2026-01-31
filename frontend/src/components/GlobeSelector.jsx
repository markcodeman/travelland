import React, { useRef, useEffect, useState, useCallback } from 'react';
import * as THREE from 'three';
import './GlobeSelector.css';

const GLOBE_COUNTRIES = {
  'France': { lat: 46.2276, lon: 2.2137, emoji: '🇫🇷', cities: ['Paris', 'Lyon', 'Marseille', 'Nice', 'Bordeaux', 'Strasbourg'] },
  'Japan': { lat: 36.2048, lon: 138.2529, emoji: '🇯🇵', cities: ['Tokyo', 'Kyoto', 'Osaka', 'Hiroshima', 'Yokohama', 'Nara'] },
  'Spain': { lat: 40.4637, lon: -3.7492, emoji: '🇪🇸', cities: ['Barcelona', 'Madrid', 'Seville', 'Valencia', 'Granada', 'Bilbao'] },
  'United Kingdom': { lat: 55.3781, lon: -3.4360, emoji: '🇬🇧', cities: ['London', 'Edinburgh', 'Manchester', 'Liverpool', 'Bath', 'Oxford'] },
  'United States': { lat: 37.0902, lon: -95.7129, emoji: '🇺🇸', cities: ['New York', 'Los Angeles', 'Chicago', 'San Francisco', 'Miami', 'New Orleans'] },
  'Italy': { lat: 41.8719, lon: 12.5674, emoji: '🇮🇹', cities: ['Rome', 'Venice', 'Florence', 'Milan', 'Naples', 'Verona'] },
  'Germany': { lat: 51.1657, lon: 10.4515, emoji: '🇩🇪', cities: ['Berlin', 'Munich', 'Hamburg', 'Frankfurt', 'Cologne', 'Dresden'] },
  'Netherlands': { lat: 52.1326, lon: 5.2913, emoji: '🇳🇱', cities: ['Amsterdam', 'Rotterdam', 'The Hague', 'Utrecht', 'Eindhoven', 'Maastricht'] },
  'Portugal': { lat: 39.3999, lon: -8.2245, emoji: '🇵🇹', cities: ['Lisbon', 'Porto', 'Faro', 'Coimbra', 'Braga', 'Madeira'] },
  'China': { lat: 35.8617, lon: 104.1954, emoji: '🇨🇳', cities: ['Shanghai', 'Beijing', 'Hong Kong', 'Guangzhou', 'Shenzhen', 'Chengdu'] },
  'India': { lat: 20.5937, lon: 78.9629, emoji: '🇮🇳', cities: ['Mumbai', 'Delhi', 'Bangalore', 'Kolkata', 'Chennai', 'Jaipur'] },
  'Brazil': { lat: -14.2350, lon: -51.9253, emoji: '🇧🇷', cities: ['Rio de Janeiro', 'São Paulo', 'Salvador', 'Brasília', 'Fortaleza', 'Recife'] },
  'Australia': { lat: -25.2744, lon: 133.7751, emoji: '🇦🇺', cities: ['Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Adelaide', 'Gold Coast'] },
  'Canada': { lat: 56.1304, lon: -106.3468, emoji: '🇨🇦', cities: ['Toronto', 'Vancouver', 'Montreal', 'Calgary', 'Ottawa', 'Quebec City'] },
  'Mexico': { lat: 23.6345, lon: -102.5528, emoji: '🇲🇽', cities: ['Mexico City', 'Guadalajara', 'Monterrey', 'Cancún', 'Playa del Carmen', 'Oaxaca'] },
  'Argentina': { lat: -38.4161, lon: -63.6167, emoji: '🇦🇷', cities: ['Buenos Aires', 'Córdoba', 'Rosario', 'Mendoza', 'La Plata', 'Mar del Plata'] },
  'South Africa': { lat: -30.5595, lon: 22.9375, emoji: '🇿🇦', cities: ['Cape Town', 'Johannesburg', 'Durban', 'Pretoria', 'Port Elizabeth', 'Bloemfontein'] }
};

const GlobeSelector = ({ onLocationChange, onCityGuide }) => {
  const mountRef = useRef(null);
  const sceneRef = useRef(null);
  const rendererRef = useRef(null);
  const cameraRef = useRef(null);
  const globeRef = useRef(null);
  const frameRef = useRef(null);
  const markersRef = useRef([]);
  const [selectedCountry, setSelectedCountry] = useState('');
  const [selectedCity, setSelectedCity] = useState('');
  const [showCityPanel, setShowCityPanel] = useState(false);
  const [sparkles, setSparkles] = useState([]);

  // Convert lat/lon to 3D coordinates
  const latLonToVector3 = useCallback((lat, lon, radius = 2) => {
    const phi = (90 - lat) * (Math.PI / 180);
    const theta = (lon + 180) * (Math.PI / 180);
    
    const x = -(radius * Math.sin(phi) * Math.cos(theta));
    const z = radius * Math.sin(phi) * Math.sin(theta);
    const y = radius * Math.cos(phi);
    
    return new THREE.Vector3(x, y, z);
  }, []);

  // Initialize Three.js scene
  useEffect(() => {
    if (!mountRef.current) return;

    console.log('🌍 Initializing Globe Selector...');
    
    // Scene setup
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0a0a1f);
    sceneRef.current = scene;

    // Camera setup
    const camera = new THREE.PerspectiveCamera(
      75,
      mountRef.current.clientWidth / mountRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.z = 6;
    cameraRef.current = camera;

    // Renderer setup
    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    mountRef.current.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    console.log('✅ Three.js scene initialized');

    // Lighting
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);
    
    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(5, 3, 5);
    scene.add(directionalLight);

    // Create globe
    const geometry = new THREE.SphereGeometry(2, 64, 64);
    const material = new THREE.MeshPhongMaterial({
      color: 0x2e7dff,
      emissive: 0x1a4d8f,
      emissiveIntensity: 0.2,
      shininess: 20,
      transparent: true,
      opacity: 0.95
    });
    
    const globe = new THREE.Mesh(geometry, material);
    scene.add(globe);
    globeRef.current = globe;

    // Add wireframe for better visibility
    const wireframeGeometry = new THREE.SphereGeometry(2.01, 32, 32);
    const wireframeMaterial = new THREE.MeshBasicMaterial({
      color: 0x4a90e2,
      wireframe: true,
      transparent: true,
      opacity: 0.1
    });
    const wireframe = new THREE.Mesh(wireframeGeometry, wireframeMaterial);
    globe.add(wireframe);

    // Add country markers
    Object.entries(GLOBE_COUNTRIES).forEach(([country, data]) => {
      const position = latLonToVector3(data.lat, data.lon);
      
      // Marker geometry - make it bigger and more visible
      const markerGeometry = new THREE.SphereGeometry(0.1, 16, 16);
      const markerMaterial = new THREE.MeshPhongMaterial({
        color: 0xffd700,
        emissive: 0xffd700,
        emissiveIntensity: 0.5
      });
      
      const marker = new THREE.Mesh(markerGeometry, markerMaterial);
      marker.position.copy(position);
      marker.userData = { country, ...data };
      scene.add(marker);
      markersRef.current.push(marker);
      
      // Add a small ring around each marker for better visibility
      const ringGeometry = new THREE.RingGeometry(0.12, 0.15, 16);
      const ringMaterial = new THREE.MeshBasicMaterial({
        color: 0xffd700,
        transparent: true,
        opacity: 0.3,
        side: THREE.DoubleSide
      });
      const ring = new THREE.Mesh(ringGeometry, ringMaterial);
      ring.position.copy(position);
      ring.lookAt(new THREE.Vector3(0, 0, 0));
      scene.add(ring);
    });

    // Add stars background
    const starsGeometry = new THREE.BufferGeometry();
    const starsMaterial = new THREE.PointsMaterial({
      color: 0xffffff,
      size: 0.02,
      transparent: true,
      opacity: 0.8
    });
    
    const starsVertices = [];
    for (let i = 0; i < 1000; i++) {
      const x = (Math.random() - 0.5) * 100;
      const y = (Math.random() - 0.5) * 100;
      const z = (Math.random() - 0.5) * 100;
      starsVertices.push(x, y, z);
    }
    
    starsGeometry.setAttribute('position', new THREE.Float32BufferAttribute(starsVertices, 3));
    const stars = new THREE.Points(starsGeometry, starsMaterial);
    scene.add(stars);

    // Mouse interaction
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    
    const handleClick = (event) => {
      const rect = renderer.domElement.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;
      
      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(markersRef.current);
      
      if (intersects.length > 0) {
        const clickedMarker = intersects[0].object;
        const { country, cities } = clickedMarker.userData;
        handleCountrySelect(country, cities);
      }
    };
    
    renderer.domElement.addEventListener('click', handleClick);

    // Animation loop
    const animate = () => {
      frameRef.current = requestAnimationFrame(animate);
      
      // Rotate globe
      if (globeRef.current) {
        globeRef.current.rotation.y += 0.005;
      }
      
      // Rotate markers with globe
      markersRef.current.forEach(marker => {
        if (marker.parent) {
          marker.rotation.y += 0.005;
        }
      });
      
      renderer.render(scene, camera);
    };
    
    animate();

    // Handle resize
    const handleResize = () => {
      if (!mountRef.current) return;
      camera.aspect = mountRef.current.clientWidth / mountRef.current.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mountRef.current.clientWidth, mountRef.current.clientHeight);
    };
    
    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      if (frameRef.current) {
        cancelAnimationFrame(frameRef.current);
      }
      if (mountRef.current && renderer.domElement) {
        mountRef.current.removeChild(renderer.domElement);
      }
      renderer.dispose();
      window.removeEventListener('resize', handleResize);
    };
  }, [latLonToVector3]);

  // Handle country selection
  const handleCountrySelect = useCallback((country, cities) => {
    setSelectedCountry(country);
    setSelectedCity('');
    setShowCityPanel(true);
    
    // Generate sparkles
    const newSparkles = Array.from({ length: 8 }, (_, i) => ({
      id: Date.now() + i,
      x: Math.random() * 100,
      y: Math.random() * 100,
      delay: Math.random() * 0.5
    }));
    setSparkles(newSparkles);
    setTimeout(() => setSparkles([]), 2000);
  }, []);

  // Handle city selection
  const handleCitySelect = useCallback((city) => {
    setSelectedCity(city);
    setShowCityPanel(false);
    
    // Trigger location change
    const countryData = GLOBE_COUNTRIES[selectedCountry];
    onLocationChange({
      country: selectedCountry,
      countryName: selectedCountry,
      city: city,
      cityName: city,
      state: '',
      stateName: '',
      neighborhood: '',
      neighborhoodName: '',
      intent: ''
    });

    // Trigger city guide
    setTimeout(() => {
      onCityGuide(city);
    }, 500);
  }, [selectedCountry, onLocationChange, onCityGuide]);

  return (
    <div className="globe-selector">
      <div className="globe-container" ref={mountRef}>
        {/* Sparkles */}
        {sparkles.map(sparkle => (
          <div
            key={sparkle.id}
            className="sparkle"
            style={{
              left: `${sparkle.x}%`,
              top: `${sparkle.y}%`,
              animationDelay: `${sparkle.delay}s`
            }}
          />
        ))}
      </div>

      {/* Instructions */}
      <div className="globe-instructions">
        <h2>🌍 Spin the World</h2>
        <p>Click on the golden markers to explore destinations</p>
      </div>

      {/* City Selection Panel */}
      {showCityPanel && (
        <div className="city-panel">
          <div className="city-panel-header">
            <h3>{selectedCountry} {GLOBE_COUNTRIES[selectedCountry]?.emoji}</h3>
            <button 
              className="close-btn"
              onClick={() => setShowCityPanel(false)}
            >
              ✕
            </button>
          </div>
          <div className="city-grid">
            {GLOBE_COUNTRIES[selectedCountry]?.cities.map(city => (
              <button
                key={city}
                className="city-card"
                onClick={() => handleCitySelect(city)}
              >
                <span className="city-name">{city}</span>
                <span className="city-sparkle">✨</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Selection Display */}
      {(selectedCountry || selectedCity) && (
        <div className="selection-display">
          {selectedCountry && (
            <div className="selection-item">
              <span>{GLOBE_COUNTRIES[selectedCountry]?.emoji}</span>
              <span>{selectedCountry}</span>
            </div>
          )}
          {selectedCity && (
            <div className="selection-item">
              <span>🏙️</span>
              <span>{selectedCity}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default GlobeSelector;
