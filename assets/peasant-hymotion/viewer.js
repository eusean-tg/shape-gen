import { createViewer } from '../preview/viewer.js';
createViewer({ examples: [...document.querySelectorAll('#version option')].map(option => ({
  id: option.value, label: option.textContent, src: 'walk/' + option.value + '/peasant-walk.glb', floorY: 0
})) });
