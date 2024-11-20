import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import './App.css';

function Home() {
  const [fadeA, setFadeA] = useState(false);
  const [slideIble, setSlideIble] = useState(false);
  const [showNav, setShowNav] = useState(false);

  useEffect(() => {
    // First fade out A
    setTimeout(() => {
      setFadeA(true);
    }, 2000);

    // Then slide 'ible'
    setTimeout(() => {
      setSlideIble(true);
    }, 2700);

    // Finally show navigation
    setTimeout(() => {
      setShowNav(true);
    }, 3400);
  }, []);

  return (
    <div className="home-container">
      <div className="center-content">
        <h1 className="animated-title">
          <span className="b-text">B</span>
          <span className={`a-text ${fadeA ? 'fade' : ''}`}>A</span>
          <span className={`ible-text ${slideIble ? 'slide' : ''}`}>
            <span className="i-letter">i</span>
            <span>ble</span>
          </span>
          <span className="study-text"> Study</span>
        </h1>
        <p className="subtitle">Powered by Artificially Divine Intelligence</p>
        
        <nav className={`main-nav ${showNav ? 'visible' : ''}`}>
          <Link to="/chat" className="nav-link">Start Bible Study</Link>
          <Link to="/about" className="nav-link">About</Link>
          <Link to="/settings" className="nav-link">Settings</Link>
        </nav>
      </div>
    </div>
  );
}

function Chat() {
  const [message, setMessage] = useState('');
  const [wsStatus, setWsStatus] = useState('Disconnected');
  const [agentMessages, setAgentMessages] = useState([]);
  const [socket, setSocket] = useState(null);

  useEffect(() => {
    const wsUrl = process.env.NODE_ENV === 'production'
      ? 'wss://api.divine-haven.org/api/v1/ws/agent'
      : 'ws://api.localhost/api/v1/ws/agent';
    
    const ws = new WebSocket(wsUrl);
    
    ws.onopen = () => {
      setWsStatus('Connected');
      console.log('WebSocket Connected');
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setAgentMessages(prev => [...prev, data]);
    };

    ws.onclose = () => {
      setWsStatus('Disconnected');
      console.log('WebSocket Disconnected');
    };

    setSocket(ws);

    return () => {
      if (ws) {
        ws.close();
      }
    };
  }, []);

  const sendMessage = (e) => {
    e.preventDefault();
    if (socket && socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({
        type: 'bible_study',
        content: message
      }));
      setMessage('');
    }
  };

  return (
    <div className="chat-container">
      <header className="chat-header">
        <Link to="/" className="back-link">← Home</Link>
        <h1>Bible Study Chat</h1>
      </header>

      <div className="chat-content">
        <div className="messages">
          {agentMessages.map((msg, index) => (
            <div key={index} className={`message ${msg.type}`}>
              <div className="content">{msg.content}</div>
            </div>
          ))}
        </div>

        <form className="input-section" onSubmit={sendMessage}>
          <textarea
            placeholder="Ask your Bible study question..."
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            rows={4}
          />
          <button type="submit" className="ask-button">
            Ask Question
          </button>
        </form>
      </div>
    </div>
  );
}

function About() {
  return (
    <div className="about-container">
      <header className="about-header">
        <Link to="/" className="back-link">← Home</Link>
        <h1>About Divine Haven</h1>
      </header>

      <div className="about-content">
        <section className="mission-section">
          <h2>Our Mission</h2>
          <p>Divine Haven bridges the timeless wisdom of scripture with modern artificial intelligence, 
          creating a unique space for deeper biblical understanding and spiritual growth.</p>
        </section>

        <section className="features-section">
          <h2>What We Offer</h2>
          <div className="features-grid">
            <div className="feature-card">
              <h3>AI-Powered Insights</h3>
              <p>Advanced AI technology provides thoughtful, contextual responses to your biblical queries, 
              helping you explore scripture from new perspectives.</p>
            </div>
            <div className="feature-card">
              <h3>Scriptural Accuracy</h3>
              <p>Our responses are grounded in careful biblical interpretation, ensuring faithful 
              representation of biblical texts and teachings.</p>
            </div>
            <div className="feature-card">
              <h3>Interactive Study</h3>
              <p>Engage in meaningful dialogue about scripture, ask questions, and receive detailed 
              explanations that deepen your understanding.</p>
            </div>
          </div>
        </section>

        <section className="values-section">
          <h2>Our Values</h2>
          <ul className="values-list">
            <li>Faithful interpretation of scripture</li>
            <li>Responsible use of AI technology</li>
            <li>Accessible biblical education</li>
            <li>Fostering spiritual growth</li>
          </ul>
        </section>
      </div>
    </div>
  );
}

function App() {
  return (
    <Router>
      <div className="App">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/about" element={<About />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;