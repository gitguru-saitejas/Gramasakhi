#!/usr/bin/env node
/** Unit checks for citizen JWT session helpers used in routing. */
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

const mod = await import(pathToFileURL(path.join(__dirname, '../src/utils/citizenSession.js')).href);

const { decodeJwtPayload, isCitizenAccessTokenValid } = mod;

function b64url(obj) {
  return Buffer.from(JSON.stringify(obj))
    .toString('base64')
    .replace(/\+/g, '-')
    .replace(/\//g, '_')
    .replace(/=+$/, '');
}

const header = b64url({ alg: 'HS256', typ: 'JWT' });
const futureExp = Math.floor(Date.now() / 1000) + 3600;
const pastExp = Math.floor(Date.now() / 1000) - 60;

const validPayload = b64url({ sub: 'cit-1', token_use: 'citizen', exp: futureExp });
const expiredPayload = b64url({ sub: 'cit-1', token_use: 'citizen', exp: pastExp });
const validToken = `${header}.${validPayload}.sig`;
const expiredToken = `${header}.${expiredPayload}.sig`;

assert.equal(isCitizenAccessTokenValid(validToken), true);
assert.equal(isCitizenAccessTokenValid(expiredToken), false);
assert.equal(decodeJwtPayload(validToken)?.sub, 'cit-1');

console.log('citizenSession routing helpers: OK');
