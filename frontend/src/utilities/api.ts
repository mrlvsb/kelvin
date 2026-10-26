export function csrfToken() {
    return document.querySelector('meta[name=csrf-token]').getAttribute('content');
}

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/**
 * Result of an API request. If `error` is set, the request has failed.
 */
export type APIResult<$ReturnType> = {
    data?: $ReturnType;
    error?: string;
};

const DEFAULT_ERROR = 'Unexpected error occurred. Please try again later.';

/**
 * Extracts a user-facing error message from a failed response.
 */
async function readErrorMessage(response: Response): Promise<string> {
    try {
        const body = await response.json();
        const message = body?.detail ?? body?.message ?? body?.error;
        if (typeof message === 'string' && message !== '') {
            return message;
        }
    } catch (error) {
        // The response does not have a valid JSON body
        console.log(`Cannot deserialize errpr response as JSON: ${error}`);
    }
    return DEFAULT_ERROR;
}

/**
 * Send a request to the API and report either the response data or an error message.
 *
 * @param url url to fetch
 * @param method HTTP method, if you want to override the default GET/POST
 * @param data data which will be sent to the API (serialized as JSON)
 * @param headers Headers for the request
 *
 * @returns `{ data }` if the request succeeded, otherwise `{ error }`
 *          with a message that can be shown to the user
 */
export const requestAPI = async <$ReturnType>(
    url: string,
    method?: Method,
    data?: unknown,
    headers?: HeadersInit
): Promise<APIResult<$ReturnType>> => {
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
            return { error: await readErrorMessage(response) };
        }

        const json = (await response.json().catch((e) => {
            console.log(`Cannot deserialize response as JSON: ${e}`);
            return undefined;
        })) as $ReturnType | undefined;
        return { data: json };
    } catch (error) {
        console.error(error);
        return { error: DEFAULT_ERROR };
    }
};

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
    const result = await requestAPI<$ReturnType>(url, method, data, headers);
    return result.error === undefined ? result.data : undefined;
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
