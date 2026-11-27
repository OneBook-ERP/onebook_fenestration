import { fitSectionAssembly } from './fitSectionAssembly'
import type { SeatingEntry } from './sectionSeating'

self.onmessage = (event: MessageEvent<SeatingEntry[]>) => {
	self.postMessage(fitSectionAssembly(event.data))
}
