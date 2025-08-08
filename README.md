--- FILE: backend/app.js ---
/*
backend/app.js
Single-file Node backend for Facebook+WhatsApp+AI demo.
Dependencies (see package.json): express, cors, mongoose, jsonwebtoken, bcryptjs, axios, socket.io, dotenv
*/

const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const mongoose = require('mongoose');
const cors = require('cors');
const jwt = require('jsonwebtoken');
const bcrypt = require('bcryptjs');
const axios = require('axios');
require('dotenv').config();

const app = express();
app.use(cors());
app.use(express.json());

// ---------- Mongoose models ----------
const { Schema } = mongoose;

const UserSchema = new Schema({
  name: String,
  email: { type: String, unique: true, sparse: true },
  phone: { type: String, unique: true, sparse: true },
  password: String,
  avatar_url: String,
  bio: String,
  createdAt: { type: Date, default: Date.now }
});

const PostSchema = new Schema({
  user: { type: Schema.Types.ObjectId, ref: 'User' },
  text: String,
  media_url: String,
  createdAt: { type: Date, default: Date.now },
  likes: [{ type: Schema.Types.ObjectId, ref: 'User' }],
  comments: [{ user: { type: Schema.Types.ObjectId, ref: 'User' }, text: String, createdAt: Date }]
});

const MessageSchema = new Schema({
  sender: { type: Schema.Types.ObjectId, ref: 'User' },
  receiver: { type: Schema.Types.ObjectId, ref: 'User' },
  text: String,
  media_url: String,
  createdAt: { type: Date, default: Date.now }
});

const GroupSchema = new Schema({
  name: String,
  description: String,
  members: [{ type: Schema.Types.ObjectId, ref: 'User' }],
  createdAt: { type: Date, default: Date.now }
});

const User = mongoose.model('User', UserSchema);
const Post = mongoose.model('Post', PostSchema);
const Message = mongoose.model('Message', MessageSchema);
const Group = mongoose.model('Group', GroupSchema);

// ---------- Database ----------
const MONGO_URI = process.env.MONGO_URI || 'mongodb://127.0.0.1:27017/chatapp';
mongoose.connect(MONGO_URI, { useNewUrlParser: true, useUnifiedTopology: true })
  .then(() => console.log('MongoDB connected'))
  .catch(err => console.error('MongoDB error', err));

// ---------- JWT middleware ----------
const JWT_SECRET = process.env.JWT_SECRET || 'CHANGE_THIS_SECRET';

function authMiddleware(req, res, next) {
  const header = req.headers.authorization;
  if (!header) return res.status(401).json({ error: 'No auth header' });
  const token = header.split(' ')[1];
  if (!token) return res.status(401).json({ error: 'Invalid auth header' });
  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    req.userId = decoded.id;
    next();
  } catch (err) {
    return res.status(401).json({ error: 'Invalid token' });
  }
}

// ---------- Routes: Auth ----------
app.post('/auth/signup', async (req, res) => {
  try {
    const { name, email, phone, password } = req.body;
    if (!password || (!email && !phone)) return res.status(400).json({ error: 'Missing credentials' });

    const hashed = await bcrypt.hash(password, 10);
    const user = new User({ name, email, phone, password: hashed });
    await user.save();
    const token = jwt.sign({ id: user._id }, JWT_SECRET, { expiresIn: '7d' });
    res.json({ user: { id: user._id, name: user.name, email: user.email, avatar_url: user.avatar_url }, token });
  } catch (err) {
    if (err.code === 11000) return res.status(400).json({ error: 'Email or phone already used' });
    res.status(500).json({ error: err.message });
  }
});

app.post('/auth/login', async (req, res) => {
  try {
    const { email, phone, password } = req.body;
    const query = email ? { email } : { phone };
    const user = await User.findOne(query);
    if (!user) return res.status(400).json({ error: 'User not found' });
    const ok = await bcrypt.compare(password, user.password);
    if (!ok) return res.status(400).json({ error: 'Invalid password' });
    const token = jwt.sign({ id: user._id }, JWT_SECRET, { expiresIn: '7d' });
    res.json({ user: { id: user._id, name: user.name, email: user.email, avatar_url: user.avatar_url }, token });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ---------- Routes: Users ----------
app.get('/users/me', authMiddleware, async (req, res) => {
  const user = await User.findById(req.userId).select('-password');
  res.json({ user });
});

// ---------- Routes: Posts (feed) ----------
app.get('/posts', authMiddleware, async (req, res) => {
  const posts = await Post.find().populate('user', 'name avatar_url').sort({ createdAt: -1 }).limit(100);
  res.json(posts);
});

app.post('/posts', authMiddleware, async (req, res) => {
  const { text, media_url } = req.body;
  const post = new Post({ user: req.userId, text, media_url });
  await post.save();
  const populated = await Post.findById(post._id).populate('user', 'name avatar_url');
  res.json(populated);
});

app.post('/posts/:id/like', authMiddleware, async (req, res) => {
  const post = await Post.findById(req.params.id);
  if (!post) return res.status(404).json({ error: 'Not found' });
  if (!post.likes.includes(req.userId)) post.likes.push(req.userId);
  await post.save();
  res.json({ success: true });
});

// ---------- Routes: Groups ----------
app.post('/groups', authMiddleware, async (req, res) => {
  const { name, description } = req.body;
  const group = new Group({ name, description, members: [req.userId] });
  await group.save();
  res.json(group);
});

app.get('/groups', authMiddleware, async (req, res) => {
  const groups = await Group.find().limit(100);
  res.json(groups);
});

// ---------- Routes: Messages ----------
app.post('/messages', authMiddleware, async (req, res) => {
  const { receiverId, text, media_url } = req.body;
  const msg = new Message({ sender: req.userId, receiver: receiverId, text, media_url });
  await msg.save();
  // emit via socket.io
  io.to(String(receiverId)).emit('message', { id: msg._id, sender: req.userId, receiver: receiverId, text, media_url, createdAt: msg.createdAt });
  res.json(msg);
});

app.get('/messages/:userId', authMiddleware, async (req, res) => {
  const other = req.params.userId;
  const messages = await Message.find({
    $or: [
      { sender: req.userId, receiver: other },
      { sender: other, receiver: req.userId }
    ]
  }).sort({ createdAt: 1 }).limit(1000);
  res.json(messages);
});

// ---------- AI assistant endpoint ----------
app.post('/ai', authMiddleware, async (req, res) => {
  try {
    const { prompt } = req.body;
    if (!process.env.OPENAI_KEY) return res.status(400).json({ error: 'OpenAI key not configured' });

    const response = await axios.post('https://api.openai.com/v1/chat/completions', {
      model: 'gpt-3.5-turbo',
      messages: [{ role: 'user', content: prompt }],
      max_tokens: 400
    }, {
      headers: { Authorization: `Bearer ${process.env.OPENAI_KEY}` }
    });

    const reply = response.data.choices?.[0]?.message?.content || '';
    res.json({ reply });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ---------- Health ----------
app.get('/', (req, res) => res.send('Backend running'));

// ---------- Socket.IO ----------
const server = http.createServer(app);
const io = socketIo(server, { cors: { origin: '*' } });

io.use(async (socket, next) => {
  const token = socket.handshake.auth?.token;
  if (!token) return next();
  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    socket.userId = decoded.id;
    next();
  } catch (err) {
    next();
  }
});

io.on('connection', (socket) => {
  if (socket.userId) socket.join(String(socket.userId));

  socket.on('sendMessage', async (payload) => {
    const message = new Message({ sender: socket.userId || payload.from, receiver: payload.to, text: payload.text, media_url: payload.media_url });
    await message.save();
    io.to(String(payload.to)).emit('message', message);
    io.to(String(message.sender)).emit('message', message);
  });

  socket.on('disconnect', () => {});
});

const PORT = process.env.PORT || 5000;
server.listen(PORT, () => console.log('Server listening on port', PORT));


--- FILE: backend/package.json ---
{
  "name": "facebook-whatsapp-ai-backend",
  "version": "1.0.0",
  "main": "app.js",
  "scripts": {
    "start": "node app.js",
    "dev": "nodemon app.js"
  },
  "dependencies": {
    "axios": "^1.6.7",
    "bcryptjs": "^2.4.3",
    "cors": "^2.8.5",
    "dotenv": "^16.3.1",
    "express": "^4.18.2",
    "jsonwebtoken": "^9.0.2",
    "mongoose": "^7.0.0",
    "socket.io": "^4.5.4"
  },
  "devDependencies": {
    "nodemon": "^3.1.0"
  }
}

--- FILE: backend/.env.example ---
MONGO_URI=your_mongodb_connection_string
JWT_SECRET=your_jwt_secret
OPENAI_KEY=your_openai_api_key
PORT=5000

--- FILE: frontend/App.js ---
/*
frontend/App.js
Single-file React Native (Expo) demo app that connects to the backend.
Replace BACKEND_URL below with your deployed backend URL or set as env var.
*/

import React, { useState, useEffect, useRef } from 'react';
import { SafeAreaView, View, Text, TextInput, Button, FlatList, TouchableOpacity, ScrollView, StyleSheet } from 'react-native';
import io from 'socket.io-client';

const BACKEND_URL = (typeof process !== 'undefined' && process.env && process.env.BACKEND_URL) ? process.env.BACKEND_URL : 'http://YOUR_BACKEND_URL:5000';

export default function App() {
  const [screen, setScreen] = useState('auth'); // auth | feed | chat
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [token, setToken] = useState(null);
  const [user, setUser] = useState(null);

  const [posts, setPosts] = useState([]);
  const [newPostText, setNewPostText] = useState('');

  const [chatWith, setChatWith] = useState('');
  const [messages, setMessages] = useState([]);
  const socketRef = useRef(null);

  useEffect(() => {
    if (token && screen === 'feed') {
      fetchPosts();
      socketRef.current = io(BACKEND_URL, { auth: { token } });
      socketRef.current.on('connect', () => console.log('socket connected'));
      socketRef.current.on('message', (m) => {
        setMessages(prev => [...prev, m]);
      });
      return () => socketRef.current.disconnect();
    }
  }, [token, screen]);

  async function signup() {
    try {
      const res = await fetch(`${BACKEND_URL}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'User', email, password })
      });
      const data = await res.json();
      if (data.token) {
        setToken(data.token); setUser(data.user); setScreen('feed');
      } else alert(JSON.stringify(data));
    } catch (err) { alert(err.message); }
  }

  async function login() {
    try {
      const res = await fetch(`${BACKEND_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
      });
      const data = await res.json();
      if (data.token) { setToken(data.token); setUser(data.user); setScreen('feed'); }
      else alert(JSON.stringify(data));
    } catch (err) { alert(err.message); }
  }

  async function fetchPosts() {
    try {
      const res = await fetch(`${BACKEND_URL}/posts`, { headers: { Authorization: `Bearer ${token}` }});
      const data = await res.json();
      setPosts(data);
    } catch (err) { console.log(err); }
  }

  async function createPost() {
    try {
      const res = await fetch(`${BACKEND_URL}/posts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ text: newPostText })
      });
      const data = await res.json();
      setPosts([data, ...posts]);
      setNewPostText('');
    } catch (err) { console.log(err); }
  }

  async function openChat(otherUserId) {
    setChatWith(otherUserId);
    setScreen('chat');
    const res = await fetch(`${BACKEND_URL}/messages/${otherUserId}`, { headers: { Authorization: `Bearer ${token}` }});
    const data = await res.json();
    setMessages(data);
  }

  function sendMessage(text) {
    if (!socketRef.current) return;
    const payload = { to: chatWith, text };
    socketRef.current.emit('sendMessage', payload);
    setMessages(prev => [...prev, { sender: user.id, receiver: chatWith, text, createdAt: new Date() }]);
  }

  if (screen === 'auth') {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.h1}>Login / Signup</Text>
        <TextInput placeholder="email" value={email} onChangeText={setEmail} style={styles.input} autoCapitalize="none" />
        <TextInput placeholder="password" value={password} onChangeText={setPassword} style={styles.input} secureTextEntry />
        <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
          <Button title="Sign Up" onPress={signup} />
          <Button title="Login" onPress={login} />
        </View>
      </SafeAreaView>
    );
  }

  if (screen === 'feed') {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.h1}>Feed</Text>
        <View style={{ marginBottom: 12 }}>
          <TextInput placeholder="Write a post..." value={newPostText} onChangeText={setNewPostText} style={styles.input} />
          <Button title="Post" onPress={createPost} />
        </View>

        <FlatList
          data={posts}
          keyExtractor={(item) => item._id || item.id}
          renderItem={({ item }) => (
            <View style={styles.post}>
              <Text style={{ fontWeight: 'bold' }}>{item.user?.name || 'User'}</Text>
              <Text>{item.text}</Text>
              <View style={{ flexDirection: 'row', marginTop: 6 }}>
                <TouchableOpacity onPress={() => openChat(item.user?._id || item.user?.id)}>
                  <Text style={styles.link}>Message</Text>
                </TouchableOpacity>
              </View>
            </View>
          )}
        />
        <Button title="Open Chat (manual)" onPress={() => setScreen('chat')} />
      </SafeAreaView>
    );
  }

  if (screen === 'chat') {
    return (
      <SafeAreaView style={styles.container}>
        <Text style={styles.h1}>Chat {chatWith ? `(with ${chatWith})` : ''}</Text>
        <ScrollView style={{ flex: 1 }}>
          {messages.map((m, i) => (
            <View key={i} style={[styles.msg, m.sender === user.id ? styles.msgSent : styles.msgRecv]}>
              <Text>{m.text}</Text>
              <Text style={styles.msgTime}>{new Date(m.createdAt).toLocaleString()}</Text>
            </View>
          ))}
        </ScrollView>
        <MessageBox onSend={sendMessage} />
        <Button title="Back to Feed" onPress={() => setScreen('feed')} />
      </SafeAreaView>
    );
  }

  return null;
}

function MessageBox({ onSend }) {
  const [text, setText] = useState('');
  return (
    <View style={styles.messageBox}>
      <TextInput value={text} onChangeText={setText} style={styles.input} placeholder="Type message..." />
      <Button title="Send" onPress={() => { if (text.trim()) { onSend(text.trim()); setText(''); } }} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 12 },
  h1: { fontSize: 22, marginBottom: 10 },
  input: { borderWidth: 1, borderColor: '#ccc', padding: 8, marginBottom: 8, borderRadius: 6 },
  post: { padding: 12, borderBottomWidth: 1, borderColor: '#eee' },
  link: { color: 'blue', marginRight: 10 },
  messageBox: { flexDirection: 'row', alignItems: 'center' },
  msg: { padding: 8, margin: 6, borderRadius: 8, maxWidth: '80%' },
  msgSent: { backgroundColor: '#dcf8c6', alignSelf: 'flex-end' },
  msgRecv: { backgroundColor: '#fff', alignSelf: 'flex-start' },
  msgTime: { fontSize: 10, color: '#666', marginTop: 4 }
});

--- FILE: frontend/package.json ---
{
  "name": "facebook-whatsapp-ai-frontend",
  "version": "1.0.0",
  "main": "node_modules/expo/AppEntry.js",
  "scripts": {
    "start": "expo start",
    "android": "expo start --android",
    "ios": "expo start --ios",
    "web": "expo start --web"
  },
  "dependencies": {
    "expo": "~48.0.0",
    "react": "18.2.0",
    "react-native": "0.71.8",
    "socket.io-client": "^4.5.4"
  }
}

--- FILE: README.md ---
# Facebook + WhatsApp + AI Demo (single-file bundle)

## What is included
- `backend/app.js` : Node single-file backend (auth, posts, messages, groups, AI endpoint, socket.io)
- `backend/package.json`
- `backend/.env.example`
- `frontend/App.js` : Single-file Expo React Native demo app
- `frontend/package.json`

## Quick start (recommended)
1. Split the bundle into files using the markers `--- FILE: <path> ---` and create files in a project.
2. Backend:
   - Create `.env` from `.env.example` and fill values:
     - `MONGO_URI`, `JWT_SECRET`, `OPENAI_KEY` (optional for AI), `PORT`
   - Install and run:
     ```
     cd backend
     npm install
     npm start
     ```
3. Frontend:
   - Use Expo: create a new Expo project or use the provided `package.json`.
   - Replace `App.js` with the provided frontend file.
   - Edit `BACKEND_URL` in `App.js` or set as environment variable to point to your backend.
   - Install dependencies and run:
     ```
     cd frontend
     npm install
     expo start
     ```

## Deploy
- Backend: deploy to Railway, Render, or any Node hosting (connect to GitHub).
- Frontend: publish with Expo (share link) or build native binaries.

## Notes
- This is a demo scaffold. For production: add validation, rate limiting, file storage, real end-to-end encryption, and secure CORS.
- If you upload the single bundle to an AI builder, instruct it to split into files using the markers. Most builders can do this automatically.

--- END OF BUNDLE ---
