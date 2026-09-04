import { createContext } from 'react';
import type { AppContextType } from './AppContext.types';

export const AppContext = createContext<AppContextType | undefined>(undefined);
