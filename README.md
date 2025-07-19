const express = require('express');
const fs = require('fs');
const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

app.get('/', (req, res) => {
  const entry = {
    time: new Date().toISOString(),
    ip: req.headers['x-forwarded-for'] || req.connection.remoteAddress,
    ua: req.get('User-Agent'),
  };
  fs.appendFileSync('logs.txt', JSON.stringify(entry) + '\n');
  res.send(`<h3>Prueba completada. Cierra esta página y revisa /logs.txt</h3>`);
});

app.get('/logs.txt', (req, res) => res.sendFile(__dirname + '/logs.txt'));

app.listen(PORT, () => console.log(`Escuchando en :${PORT}`));
