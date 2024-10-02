type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/**
 * Get data from API
 * @param url url to fetch
 * @param data data which will be sent to the API
 * @param method HTTP method, if you want to override the default GET/POST
 * @note If data is passed, the request will be a POST request, otherwise a GET request, if not overridden by method parameter
 * @returns $ReturnType, if the request was successful, otherwise undefined
 */
export const getFromAPI = async <$ReturnType>(
    url: string,
    data?: unknown,
    method?: Method
): Promise<$ReturnType | undefined> => {
    try {
        const response = await fetch(url, {
            method: method || (data ? 'POST' : 'GET'),
            body: data ? JSON.stringify(data) : undefined
        });

        if (!response.ok) {
            return undefined;
        }

        const json = await response.json();
        return json as $ReturnType;
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
    } catch (_) {
        return undefined;
    }
};

/**
 * Generate array with range of numbers from start
 * @param size size of the array
 * @param start starting number
 * @returns array of numbers from start to start + size
 */
export const generateRange = (size: number, start = 0) => {
    return Array.from({ length: size }).map((_, i) => i + start);
};

/**
 * Generate string date format from date
 * @param date Date object or string in format 'YYYY-MM-DD' or 'YYYY-MM-DDTHH:MMZ'
 * @param withTime Include time in the output
 * @returns If withTime is false 'YYYY-MM-DD', otherwise 'YYYY-MM-DD HH:MM'
 */
export const getDate = (date: Date | string, withTime = false) => {
    let d: Date;
    if (typeof date === 'string') {
        d = new Date(date);
    } else {
        d = date;
    }

    const year = d.getFullYear();
    const month = (d.getMonth() + 1).toString().padStart(2, '0');
    const day = d.getDate().toString().padStart(2, '0');

    if (!withTime) {
        return `${year}-${month}-${day}`;
    }

    const hours = d.getHours().toString().padStart(2, '0');
    const minutes = d.getMinutes().toString().padStart(2, '0');
    return `${year}-${month}-${day} ${hours}:${minutes}`;
};
