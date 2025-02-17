import { vi } from 'vitest';

/**
 * Mock fetch requests
 * Currently accept one parameter, which is object, mapping url to
 * response object, which consists of okStatus and return data
 * returned by json() method
 */
export const mockFetch = (
    urlsMap: Record<
        string,
        {
            okStatus: boolean;
            data: unknown;
        }
    >
) => {
    const keys = Object.keys(urlsMap);

    vi.stubGlobal(
        'fetch',
        vi.fn((url: string) => {
            if (!keys.includes(url)) {
                return Promise.resolve({
                    ok: false,
                    json: () => Promise.resolve(undefined)
                });
            }

            const resultData = urlsMap[url];

            return Promise.resolve({
                ok: resultData.okStatus,
                json: () => Promise.resolve(resultData.data)
            });
        })
    );
};
