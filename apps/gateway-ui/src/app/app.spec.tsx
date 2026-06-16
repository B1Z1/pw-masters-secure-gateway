import { render } from '@testing-library/react';

import App from './app';

describe('App', () => {
  it('should render successfully', () => {
    const { baseElement } = render(<App />);
    expect(baseElement).toBeTruthy();
  });

  it('should have the gateway title', () => {
    const { getAllByText } = render(<App />);
    expect(
      getAllByText(new RegExp('LLM Gateway', 'gi')).length > 0,
    ).toBeTruthy();
  });
});
