import { voiceClient } from "./client.js";

import tokens from "./tokens.js";

import express from 'express';

const app = express();

const port = 3000;

let url = "";

let uptimeDate = Date.now();

let requests = 0;

let response = null;

app.use((req, res, next) => {

    const hostname = req.hostname;

    const subdomain = hostname.split('.')[0];

    const domain = hostname.replace(`${subdomain}.`, '');

    req.subdomain = subdomain;

    req.domain = domain;

    url = `https://${subdomain}.${domain}/`;

    next();

});

app.get('/', (req, res) => res.send('Hello World!'));

app.listen(port, () => console.log(`Example app listening at ${url}`));

process.on('uncaughtException', (err) => {

    console.error(`Uncaught Exception: ${err.message}`);

});

process.on('unhandledRejection', (reason, promise) => {

    console.error('Unhandled Rejection at:', promise, 'reason:', reason);

});

setInterval(async () => {

    console.log(url);

    try {

        response = await fetch(url, { method: 'HEAD' });

        requests += 1;

        console.log(`Request done with status ${response.status} ${requests}`);

    } catch (error) {

        if (error.response) {

            requests += 1;

            console.log(`Response status: ${error.response.status}${requests}`);

        }

    } finally {

        response = null;

    }

}, 15000);

const cleanTokens = tokens.reduce((acc, token) => {

    const isValid = token?.token?.length > 30;

    const isDuplicate = acc.some(t => t.token === token.token);

    if (isValid && !isDuplicate) {

        acc.push(token);

    }

    else {

        console.warn('Invalid or duplicate token configuration:', token);

    }

    return acc;

}, []);

for (const token of cleanTokens) {

    const client = new voiceClient(token);

    client.on('ready', (user) => {

        console.log(`Logged in as ${user.username}#${user.discriminator}`);

    });

    client.on('connected', () => {

        console.log('Connected to Discord');

    });

    client.on('disconnected', () => {

        console.log('Disconnected from Discord');

    });

    client.on('voiceReady', () => {

        console.log('Voice is ready');

    });

    client.on('error', (error) => {

        console.error('Error:', error);

    });

    client.on('debug', (message) => {

        console.debug(message);

    });

    client.connect();

}

