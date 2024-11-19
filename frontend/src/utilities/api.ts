export function csrfToken() {
    return document.querySelector('meta[name=csrf-token]').getAttribute('content');
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/**
 * Get data from API
 *
 * @param url url to fetch
 * @param data data which will be sent to the API
 * @param method HTTP method, if you want to override the default GET/POST
 * @note If data is passed, the request will be a POST request, otherwise a GET request, if not overridden by method parameter
 * @param headers Headers for the request
 *
 * @returns $ReturnType, if the request was successful, otherwise undefined
 */
export const getFromAPI = async <$ReturnType>(
    url: string,
    method?: Method,
    data?: unknown,
    headers?: HeadersInit
): Promise<$ReturnType | undefined> => {
    try {
        const response = await fetch(url, {
            method: method || (data ? 'POST' : 'GET'),
            headers,
            body: data ? JSON.stringify(data) : undefined
        });

        if (!response.ok) {
            return undefined;
        }

        const json = await response.json();
        return json as $ReturnType;
    } catch (error) {
        console.error(error);
        return undefined;
    }
};

/**
 * Get data from endpoint with {@link getFromAPI()}, but with already filled header `X-CSRFToken`.
 *
 * @param url url to fetch
 * @param data data which will be sent to the API
 * @param method HTTP method, if you want to override the default GET/POST
 * @note If data is passed, the request will be a POST request, otherwise a GET request, if not overridden by method parameter
 * @param headers Headers for the request
 *
 * @returns $ReturnType, if the request was successful, otherwise undefined
 */
export const getDataWithCSRF = async <$ReturnType>(
    url: string,
    method?: Method,
    data?: unknown,
    headers?: HeadersInit
): Promise<$ReturnType | undefined> => {
    const CSRF = {
        'X-CSRFToken': csrfToken()
    };
    return getFromAPI(url, method, data, headers ? { ...headers, ...CSRF } : CSRF);
};
