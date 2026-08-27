export function csrfToken() {
    return document.querySelector('meta[name=csrf-token]').getAttribute('content');
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/**
 * Get data from API
 *
 * @param url url to fetch
 * @param data data which will be sent to the API (serialized as JSON)
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
        const hasBody = data !== undefined && data !== null;
        if (hasBody) {
            headers = { 'Content-Type': 'application/json', ...headers };
        }

        const response = await fetch(url, {
            method: method || (hasBody ? 'POST' : 'GET'),
            headers,
            body: hasBody ? JSON.stringify(data) : undefined
        });

        if (!response.ok) {
            return undefined;
        }

        return (await response.json().catch((e) => {
            console.log(`Cannot deserialize response as JSON: ${e}`);
            return undefined;
        })) as $ReturnType | undefined;
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

/**
 * Send a `multipart/form-data` request with the CSRF token attached. Such
 * requests always mutate server state, so the CSRF token is always included and
 * the method defaults to POST. The browser sets the `Content-Type` (including
 * the multipart boundary) from the {@link FormData} body, so it is not set here.
 *
 * @param url url to fetch
 * @param form form data to send as the request body
 * @param method HTTP method (defaults to POST)
 *
 * @returns parsed JSON response, or undefined if the request failed or the
 *          response had no JSON body
 */
export const sendFormWithCSRF = async <$ReturnType>(
    url: string,
    form: FormData,
    method: Method = 'POST'
): Promise<$ReturnType | undefined> => {
    try {
        const response = await fetch(url, {
            method,
            headers: { 'X-CSRFToken': csrfToken() },
            body: form
        });

        if (!response.ok) {
            return undefined;
        }

        return (await response.json().catch((e) => {
            console.log(`Cannot deserialize response as JSON: ${e}`);
            return undefined;
        })) as $ReturnType | undefined;
    } catch (error) {
        console.error(error);
        return undefined;
    }
};
