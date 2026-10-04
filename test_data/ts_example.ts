// Sample TypeScript file testing ES6 imports, CommonJS requires, and dynamic imports

import React, { useState, useEffect } from 'react';
import { helper_function } from './utils';
import '../scanner/CMakeLists.txt';
const express = require('express');
const path = require('path');
export { helper_function } from './utils';
export * from './local_header.h';

async function loadDynamic() {
    const module = await import('./lazy_module');
    return module;
}
