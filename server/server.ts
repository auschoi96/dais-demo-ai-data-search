import { createApp, analytics, server } from '@databricks/appkit';
import { searchPlugin } from './plugins/search.js';

createApp({
  plugins: [
    analytics(),
    searchPlugin(),
    server(),
  ],
})
  .catch(console.error);
